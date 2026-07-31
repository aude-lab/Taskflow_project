# SPEC — Assistant conversationnel de planification (chat IA)

## 1. Objectif & vision

Faire évoluer la feature IA d'un simple générateur (texte → tâches) vers un
**assistant conversationnel** qui aide à définir un projet complet par le
dialogue, puis crée le projet et ses tâches.

Deux points d'entrée :
- **Nouveau projet** : page de chat dédiée `/assistant/`. L'IA pose des
  questions (nom, objectif, deadline, type de tâches…), l'utilisateur répond
  librement, jusqu'à un récapitulatif validable.
- **Projet existant** : bouton « Réajuster avec l'IA » sur la page détail d'un
  projet → même chat, mais les **tâches existantes** sont injectées dans le
  contexte système.

Le workflow classique (création manuelle, `generate`/`confirm`) reste **intact**
et coexiste (cf. §6).

## 2. Deux décisions d'architecture à valider

### D1 — Création d'un *nouveau* projet à la confirmation

`/api/tasks/confirm/` (existant, testé) crée des tâches dans un projet
**déjà existant** (`project_id` requis, `for_user` → 404). Le flux « nouveau
projet » doit d'abord **créer le projet**. Deux cas :

- **Projet existant** (réajustement) : la confirmation appelle directement
  `/api/tasks/confirm/` avec le `project_id`. Réutilisation telle quelle. ✅
- **Nouveau projet** : le front crée d'abord le projet via
  `POST /api/projects/` (CRUD existant, `owner` fixé serveur), récupère son
  `id`, puis appelle `/api/tasks/confirm/` avec cet `id`.

> **Conséquence :** `ProjectViewSet` doit accepter la `SessionAuthentication`
> (aujourd'hui JWT seul) pour être appelable en `fetch` depuis le front, comme
> on l'a fait pour les endpoints IA. Ajout **additif** (`authentication_classes`
> par vue), sans changer le comportement CRUD.
>
> **Limite assumée (V1) :** l'enchaînement projet puis tâches n'est pas atomique
> entre deux requêtes HTTP. Si la création des tâches échoue après celle du
> projet, l'utilisateur se retrouve avec un projet vide (récupérable : il peut
> réessayer ou le supprimer). Le front gère l'erreur en l'informant, avec le
> lien vers le projet créé.
>
> *Alternative écartée pour rester dans la consigne « réutiliser l'existant » :*
> un endpoint dédié `confirm` créant projet+tâches en une transaction atomique.
> Plus propre sur l'atomicité, mais duplique la logique de `confirm`. **À
> trancher par Aude.**

### D2 — Ordre d'authentification (401 vs 403)

Comme pour `generate`/`confirm` : `authentication_classes =
[JWTAuthentication, SessionAuthentication]` (JWT en tête pour un **401** sur
anonyme, cf. SPEC-ai-assistant §3), `IsAuthenticated`, CSRF géré côté front.

## 3. Endpoint `POST /api/chat/`

| Méthode | URL | Permission | Écrit en base ? |
|---------|-----|------------|-----------------|
| POST | `/api/chat/` | `IsAuthenticated` | **Non** |

`APIView` dans `tasks/views.py`, `path()` explicite dans `tasks/urls.py`. Ne
crée **rien** : la création passe par les endpoints existants (§2).

### Entrée
```json
{
  "messages": [
    {"role": "user", "content": "Je veux organiser un événement"},
    {"role": "assistant", "content": "Quel est le nom du projet ?"},
    {"role": "user", "content": "Lancement produit, pour fin septembre"}
  ],
  "project_id": null
}
```
- `messages` : historique complet renvoyé par le front à chaque appel (pas de
  mémoire serveur — cf. §6). Liste non vide de `{role, content}` ; `role` ∈
  `user`/`assistant`. Validé par un serializer d'entrée.
- `project_id` : `null` (nouveau projet) ou l'`id` d'un projet de l'utilisateur.
  Si fourni → chargé via `for_user` (**404** si absent/autrui), ses tâches sont
  injectées dans le prompt système (§4).

### Sortie (200)
Le modèle répond **toujours** en JSON structuré (via `response_format`
`json_object`), jamais en texte libre — ce qui rend la sortie prévisible :
```json
{
  "reply": "message conversationnel en français, affiché dans le chat",
  "ready_to_confirm": false,
  "proposal": null
}
```
Quand l'IA a assez d'infos :
```json
{
  "reply": "Voici le plan que je te propose…",
  "ready_to_confirm": true,
  "proposal": {
    "project": {"name": "Lancement produit", "description": "…"},
    "tasks": [
      {"title": "…", "description": "…", "priority": "haute",
       "status": "a_faire", "due_date": "2026-09-15"}
    ]
  }
}
```
- `proposal.tasks` : **normalisées côté serveur** par `_normalize_task`
  (réutilisé de `tasks/ai.py` : priority/status hors-choices → défauts,
  due_date vide → null). Le contrat de valeurs est identique à `generate`.
- Sur réajustement (`project_id` fourni), le front envoie `proposal.tasks` à
  `/api/tasks/confirm/` avec ce `project_id` : seules des **nouvelles** tâches
  sont créées (le chat ne modifie/supprime pas l'existant — cf. §7).

### Erreurs
- `400` : `messages` vide/malformé (serializer).
- `404` : `project_id` d'un autre utilisateur / inexistant.
- `401` : non authentifié.
- `502` : OpenAI injoignable/timeout **ou** réponse non exploitable (JSON
  invalide / structure inattendue). Jamais de 500 silencieux. Réutilise
  `AIServiceError` (le champ `unparseable` peut mapper 502 ici : en mode chat, un
  JSON cassé est un dysfonctionnement du service, pas une faute du client).

## 4. Prompt système (instructions données à l'IA)

Vit dans `tasks/ai.py` (module qui isole déjà OpenAI). Contenu :

- **Rôle** : assistant de planification de projet pour TaskFlow. Toujours
  répondre **en français**.
- **Objectif de conversation** : collecter nom du projet, objectif, type de
  tâches, priorités, deadlines — en **2 à 4 échanges maximum**, sans
  interrogatoire inutile.
- **Format de sortie imposé** : répondre UNIQUEMENT avec l'objet JSON décrit au
  §3 (`reply`, `ready_to_confirm`, `proposal`), sans texte hors JSON, sans bloc
  Markdown. `reply` porte le message affiché à l'utilisateur.
- **Quand proposer** : dès qu'il a assez d'infos, mettre `ready_to_confirm:
  true` et remplir `proposal` (projet + liste de tâches). Sinon `false` et
  `proposal: null`.
- **Valeurs exactes des choices** (ASCII sans accents) : priority ∈
  `basse|moyenne|haute`, status ∈ `a_faire|en_cours|termine`, due_date en
  `AAAA-MM-JJ` ou null. Défauts : `moyenne`, `a_faire`, null.
- **Date du jour injectée** (comme `generate`) : « Nous sommes le <AAAA-MM-JJ> »
  + consigne de résoudre les dates relatives sans échéance passée.
- **Contexte projet existant** (si `project_id`) : injecter la liste des tâches
  actuelles (titre, statut, priorité, échéance) et préciser que la proposition
  vient **compléter** ce projet, pas le recréer.

## 5. Front

### 5.1 Page `/assistant/` (nouveau)
Vue Django `TemplateView` (`LoginRequiredMixin`), URL `name="assistant"`,
template `assistant.html`. JS vanilla, dans l'esprit de la section IA existante.

- **Fil de discussion** : bulles alternées (user à droite, assistant à gauche).
  L'historique vit dans un **tableau JS** (`messages`), renvoyé entier à chaque
  `POST /api/chat/` (avec `X-CSRFToken`). Disparaît à la fermeture de la page.
- **Message d'accueil** de l'assistant affiché au chargement (côté front, sans
  appel API), pour amorcer.
- **Zone de saisie** + bouton Envoyer : à l'envoi, on pousse le message user,
  on appelle l'API, on affiche `reply`. **État de chargement** visible (bulle
  « … » / bouton désactivé). **Erreurs réseau/API** affichées clairement.
- **Récapitulatif** : quand `ready_to_confirm: true`, afficher le `proposal`
  (nom du projet + tâches : titre, priorité, échéance) et un bouton
  **« Confirmer et créer »**. L'utilisateur peut aussi continuer à écrire pour
  demander des modifications (nouvel appel chat → nouvelle proposition).
- **Confirmation** (nouveau projet) : `POST /api/projects/` → puis
  `POST /api/tasks/confirm/` avec le nouvel `id` → **redirect** vers
  `/projets/<id>/`. Échec après création projet : message + lien vers le projet.
- Échappement HTML de tout contenu injecté (anti-XSS), comme la feature
  existante.

### 5.2 Page d'accueil — deux modes
Sur `core/templates/core/home.html`, **au-dessus** du tableau de bord, un encart
avec deux actions :
- **« Commencer avec l'assistant IA »** → `/assistant/`.
- **« Créer un projet manuellement »** → `project_create` (existant).

Le tableau de bord reste affiché en dessous (aucune régression).

### 5.3 Page détail projet — « Réajuster avec l'IA »
Sur `projects/templates/projects/project_detail.html`, à côté de la section IA
existante, un bouton **« Réajuster avec l'IA »** → `/assistant/?project_id=<pk>`.
La page chat lit le `project_id` (query param, injecté par le template ou lu en
JS) et l'envoie à `/api/chat/`, ce qui déclenche l'injection des tâches
existantes.

> La section « Générer des tâches avec l'IA » (generate/confirm) reste en place :
> chat et génération one-shot coexistent (cf. §6).

## 6. Ce qui change par rapport à l'existant

| Élément | Statut |
|---------|--------|
| `POST /api/tasks/generate/` | **Inchangé** (génération one-shot depuis un texte) |
| `POST /api/tasks/confirm/` | **Inchangé**, réutilisé par le chat pour les tâches |
| Section « Générer des tâches avec l'IA » (détail projet) | **Conservée** |
| `_normalize_task`, prompt/date de `tasks/ai.py` | **Réutilisés** par le chat |
| `POST /api/chat/` | **Nouveau** |
| Page `/assistant/` + entrées (accueil, détail projet) | **Nouveau** |
| `ProjectViewSet` | **Modif additive** : ajout `SessionAuthentication` (D1) |

Aucune suppression : la V1 IA reste fonctionnelle, le chat s'ajoute par-dessus.

## 7. Hors scope

- Mémoire de conversation **persistante** en base (l'historique vit côté front).
- Plusieurs conversations **en parallèle** / reprise d'une conversation passée.
- **Modification/suppression** des tâches existantes via le chat (le chat ne
  fait qu'**ajouter** ; réajuster = proposer de nouvelles tâches).
- Streaming de la réponse (réponse en un bloc).

## 8. Cas limites & tests (OpenAI **toujours mocké**)

| # | Cas | Attendu |
|---|-----|---------|
| 1 | Conversation en cours (mock : JSON `ready_to_confirm:false`) | 200, `reply` non vide, `proposal` null, **rien créé** |
| 2 | Proposition finale (mock : JSON `ready_to_confirm:true` + proposal) | 200, `proposal.project` + `proposal.tasks` normalisées |
| 3 | Proposition avec valeurs hors-choices dans le mock | tasks normalisées (moyenne / a_faire / null) |
| 4 | `project_id` d'un projet existant de l'utilisateur | 200 ; le prompt système contient les tâches existantes (inspection des `messages` passés au client mocké) |
| 5 | `project_id` d'un autre utilisateur | **404** |
| 6 | OpenAI injoignable / timeout | **502** + message clair, pas de 500 |
| 7 | Réponse OpenAI non parseable | **502** + message clair |
| 8 | Non authentifié | **401** |
| 9 | `messages` vide / champ manquant | **400** |
| 10 | `ProjectViewSet` accepte une création en session (CSRF) | 201 (garantit le flux « nouveau projet ») |

## 9. Fichiers touchés

- `tasks/ai.py` — `chat(messages, project_tasks=None)` : prompt système chat,
  appel OpenAI, parsing du JSON `{reply, ready_to_confirm, proposal}`, réutilise
  `_normalize_task` et l'injection de date.
- `tasks/views.py` — `ChatView` (session+JWT).
- `tasks/serializers.py` — serializer d'entrée du chat (`messages`, `project_id`).
- `tasks/urls.py` — `path("chat/", …)`.
- `projects/views.py` — `authentication_classes` sur `ProjectViewSet` (D1).
- `core/templates/core/home.html` — encart deux modes.
- `projects/templates/projects/project_detail.html` — bouton « Réajuster ».
- `core/views_web.py` (ou `tasks`) + `urls_web` + `assistant.html` — page chat.
- `tasks/tests.py` — cas §8.
