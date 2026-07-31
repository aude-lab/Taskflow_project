# SPEC — Assistant IA (génération de tâches en langage naturel)

## 1. Objectif

Depuis la page détail d'un projet, permettre à l'utilisateur de décrire ses
tâches en langage naturel, obtenir un **aperçu** de tâches structurées proposées
par l'IA (OpenAI `gpt-4o-mini`), en sélectionner un sous-ensemble, puis les
créer réellement en base. **Aucune création tant que l'utilisateur n'a pas
confirmé.**

## 2. Périmètre

Dans le périmètre :
- 2 endpoints DRF : `generate` (aperçu, sans écriture) et `confirm` (création).
- Section IA sur la page détail projet (bouton + textarea + aperçu + sélection).
- Gestion d'erreurs OpenAI (indisponibilité, JSON invalide, timeout).
- Tests avec appel OpenAI **mocké** (jamais d'appel réel en test).

**Hors scope** (explicite) : modifier/supprimer des tâches via l'IA, génération
multi-projets en une passe, historique/persistance des générations.

## 3. Décision d'architecture : authentification

L'API DRF est configurée en **JWT uniquement** (`DEFAULT_AUTHENTICATION_CLASSES`),
alors que le front est rendu par des vues Django classiques en **session**. Un
`fetch` depuis le navigateur envoie le cookie de session, pas de JWT.

**Décision :** les deux nouveaux endpoints déclarent explicitement
`authentication_classes = [JWTAuthentication, SessionAuthentication]` (par vue,
sans toucher au réglage global). Le front les appelle en session ; le
`SessionAuthentication` de DRF impose alors le **CSRF**, donc le `fetch` envoie
l'en-tête `X-CSRFToken`. Un `IsAuthenticated` couvre le cas non authentifié.

> **Ordre JWT en tête (important).** DRF dérive le choix **401 vs 403** de
> l'en-tête d'authentification du *premier* authenticator. `SessionAuthentication`
> n'en fournit pas (→ 403) ; `JWTAuthentication` fournit `Bearer` (→ 401). Pour
> obtenir le **401** attendu au §8 sur un accès anonyme, JWT doit donc être en
> tête. L'ordre n'affecte pas la réussite de l'authentification (les deux sont
> tentés), et la Session impose toujours le CSRF quand c'est elle qui authentifie.

> Alternative écartée : faire obtenir un JWT au front. Plus lourd (stockage du
> token, refresh) pour un front qui vit déjà en session — sur-ingénierie ici.

## 4. Endpoints

| Méthode | URL | Permission | Écrit en base ? |
|---------|-----|------------|-----------------|
| POST | `/api/tasks/generate/` | `IsAuthenticated` | Non |
| POST | `/api/tasks/confirm/` | `IsAuthenticated` | Oui |

Deux actions POST hors CRUD : deux `APIView` dans `tasks/views.py`, câblées par
des `path()` explicites dans `tasks/urls.py` (comme `DashboardView`). Le préfixe
`tasks/` est choisi pour la cohérence, mais ces routes doivent être déclarées
**avant** le router `DefaultRouter` (ou avec des chemins ne pouvant entrer en
collision avec `tasks/<pk>/`) — `generate/` et `confirm/` ne sont pas des pk, il
n'y a donc pas de collision, mais on garde les `path()` explicites en tête.

### 4.1 `POST /api/tasks/generate/`

**Requête :**
```json
{ "text": "...", "project_id": 12 }
```

**Traitement :**
1. Valider la présence de `text` (non vide, après strip) et `project_id`.
2. Charger le projet via `Project.objects.for_user(request.user)` →
   **404 si absent/appartenant à autrui** (on ne révèle pas son existence, comme
   partout ailleurs). *(Le sujet mentionne 400/403 ; on retient 404 pour rester
   cohérent avec la convention du projet — à valider par Aude.)*
3. Appeler OpenAI (`gpt-4o-mini`) avec un **prompt système** exigeant en retour
   **UNIQUEMENT** un JSON valide : une liste d'objets tâche. Timeout **10 s**.
4. Parser la réponse ; **normaliser/valider** chaque tâche (voir §5).
5. Renvoyer la liste **sans rien créer**.

**Réponse 200 :**
```json
{ "tasks": [ { "title": "...", "description": "...", "priority": "moyenne",
              "status": "a_faire", "due_date": "2026-08-15" }, ... ] }
```

**Réponses d'erreur :**
- `400` : `text` manquant/vide, ou JSON OpenAI non parseable/non conforme.
- `404` : projet inexistant ou d'un autre utilisateur.
- `502` (ou `503`) : OpenAI injoignable / timeout — message clair. *(Choix
  502/503 vs 400 à valider ; 400 conviendrait aussi si on préfère ne pas
  distinguer. Aucun 500 silencieux dans tous les cas.)*

### 4.2 `POST /api/tasks/confirm/`

**Requête :**
```json
{ "project_id": 12,
  "tasks": [ { "title": "...", "description": "...", "priority": "haute",
               "status": "a_faire", "due_date": "2026-08-15" }, ... ] }
```

**Traitement :**
1. Recharger le projet via `for_user()` → **404 si autrui** (on **ne fait jamais
   confiance** au `project_id` du client : re-vérification systématique).
2. **Re-valider** chaque tâche via le `TaskSerializer` existant (choices,
   longueurs, format de date) — les données viennent du client, pas de l'IA
   directement. Une tâche invalide → **400**, aucune création (tout ou rien,
   dans une transaction).
3. Créer chaque tâche rattachée au projet (`project` fixé côté serveur, jamais
   pris du corps de la tâche).

**Réponse 201 :** la liste des tâches créées (sérialisées par `TaskSerializer`,
avec leur `id`).

## 5. Contrat de données IA (choices)

Le prompt système impose des valeurs **conformes aux `choices` du modèle `Task`,
en ASCII sans accents** :

| Champ | Valeurs autorisées | Défaut si absent/invalide |
|-------|--------------------|---------------------------|
| `title` | chaîne non vide, ≤ 200 | obligatoire (sinon tâche ignorée/400) |
| `description` | chaîne (peut être vide) | `""` |
| `priority` | `basse`, `moyenne`, `haute` | `moyenne` |
| `status` | `a_faire`, `en_cours`, `termine` | `a_faire` |
| `due_date` | `AAAA-MM-JJ` ou `null` | `null` |

La validation finale reste **côté serveur** (`TaskSerializer`) : le prompt guide
l'IA, il ne la remplace pas. Une valeur hors-choices renvoyée par l'IA est soit
normalisée au défaut, soit rejetée — comportement à trancher, mais **jamais**
stockée telle quelle.

## 6. Configuration

- `.env` : `OPENAI_API_KEY=` (+ ligne ajoutée à `.env.example`, sans valeur).
- `settings.py` : `OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')`.
- `requirements.txt` : ajouter `openai`.
- Le code appelant lit la clé depuis `settings`, pas `os.environ` directement.
- Le client OpenAI et le prompt système vivent dans un module dédié
  (`tasks/ai.py`) pour isoler la dépendance externe et faciliter le mock en test.

## 7. Front (page détail projet)

Sur `projects/templates/projects/project_detail.html` :
1. Bouton **« Générer des tâches avec l'IA »** → révèle une section (masquée par
   défaut) contenant un `<textarea>` (placeholder « Décris tes tâches en langage
   naturel… ») et un bouton **« Analyser »**.
2. « Analyser » → `fetch POST /api/tasks/generate/` (`X-CSRFToken`, cookie de
   session) avec `{ text, project_id }`. Pendant l'appel : état de chargement,
   bouton désactivé.
3. Aperçu : liste des tâches proposées (titre, priorité, échéance) chacune avec
   une **case à cocher** (cochées par défaut). Bouton **« Créer les tâches
   sélectionnées »** (désactivé si aucune sélection).
4. « Créer… » → `fetch POST /api/tasks/confirm/` avec `{ project_id, tasks }`
   (seulement les tâches cochées) → au 201, **rechargement de la page** pour que
   les nouvelles tâches apparaissent dans le tableau existant.
5. Le JS est minimal et vit dans un `{% block %}` de la page détail (ou un petit
   fichier statique) ; le `project_id` et le token CSRF sont injectés par le
   template.

**Erreurs front :** tout code non-2xx ou échec réseau → message d'erreur clair
et lisible dans la section (pas d'échec silencieux, pas de page blanche).

## 8. Cas limites & tests (OpenAI **mocké**)

Appel OpenAI toujours mocké — **jamais** d'appel réel en test.

| # | Cas | Attendu |
|---|-----|---------|
| 1 | `generate` valide (mock renvoie un JSON de tâches) | 200 + liste, **0 tâche créée** en base |
| 2 | `generate` avec `project_id` d'un autre utilisateur | 404 (cf. §4.1, à valider) |
| 3 | `generate`, OpenAI renvoie du texte non parseable | 400 + message clair, pas de 500 |
| 4 | `generate`, OpenAI lève une exception / timeout | 502/503 + message clair |
| 5 | `generate`, `text` vide/manquant | 400 |
| 6 | `confirm` valide | 201 + tâches créées, rattachées au bon projet |
| 7 | `confirm` avec `project_id` d'un autre utilisateur | 404, **aucune** création |
| 8 | `confirm` avec une tâche invalide (choices/date) | 400, **aucune** création (transaction) |
| 9 | non authentifié sur `generate` **et** `confirm` | 401 |

## 9. Fichiers touchés

- `tasks/ai.py` *(nouveau)* — client OpenAI + prompt système + parsing.
- `tasks/views.py` — `GenerateTasksView`, `ConfirmTasksView`.
- `tasks/urls.py` — 2 `path()`.
- `tasks/serializers.py` — éventuel serializer d'entrée léger (validation
  `text`/`project_id`), réutilise `TaskSerializer` pour la sortie/création.
- `tasks/tests.py` — cas §8.
- `projects/templates/projects/project_detail.html` — section IA + JS.
- `settings.py`, `.env.example`, `requirements.txt` — config.
