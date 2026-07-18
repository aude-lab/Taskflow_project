# SPEC — Filtres sur la liste des tâches

## 1. Objectif

Permettre de filtrer `GET /api/tasks/` par projet, statut, priorité et échéance, pour préparer les vues de suivi (tâches en retard, à venir, par statut).

## 2. Portée

- **Uniquement la liste des tâches** (`GET /api/tasks/`). Les projets ne sont pas filtrables en V1 (les critères demandés sont tous des attributs de tâche).
- Les filtres s'appliquent **après** le filtrage de sécurité par utilisateur (`get_queryset` reste la base) : on ne filtre jamais au-delà des tâches déjà visibles par l'utilisateur.

## 3. Paramètres de requête

Tous optionnels, combinables (logique **ET**). Aucun paramètre → comportement actuel inchangé.

| Paramètre | Type | Effet |
|-----------|------|-------|
| `project` | id | tâches de ce projet |
| `status` | choice (`a_faire`/`en_cours`/`termine`) | tâches de ce statut |
| `priority` | choice (`basse`/`moyenne`/`haute`) | tâches de cette priorité |
| `due_date_before` | date `YYYY-MM-DD` | échéance ≤ cette date (inclus) |
| `due_date_after` | date `YYYY-MM-DD` | échéance ≥ cette date (inclus) |

Pas de filtre d'égalité exacte sur `due_date` : seules les bornes sont exposées (ce sont elles qui servent aux vues de suivi).

`due_date_before` / `due_date_after` sont les briques des vues « en retard » (`due_date_before=<aujourd'hui>`) et « à venir » (`due_date_after=<aujourd'hui>`) — le calcul de « aujourd'hui » et la composition de ces vues relèvent du **tableau de bord**, pas de ce spec.

## 4. Comportements attendus

- **Valeur invalide** d'un `status`/`priority` (hors choices) ou d'une date mal formée → **400**, message de champ clair.
- **`project` inexistant ou appartenant à un autre utilisateur** → **résultat vide** (`[]`), pas une erreur : le filtre restreint un queryset déjà limité à l'utilisateur, un id hors de sa portée ne matche simplement rien. Les deux cas (inexistant / autrui) doivent produire **exactement la même réponse `200 []`** : une divergence (ex. 400 pour l'inexistant, 200 pour l'autrui) serait un **oracle** révélant l'existence des projets d'autrui. En pratique, `project` est un `NumberFilter` et non un `ModelChoiceFilter` (ce dernier valide contre `Project.objects.all()` et réintroduirait l'oracle). Un `project` non numérique (`abc`) → 400 (erreur de type, sans rapport avec l'existence).
- Filtres combinés → intersection (ET).
- Le filtrage n'introduit **aucune requête N+1** (le `select_related('project')` existant est conservé).

## 5. Choix d'implémentation

**Décidé (2026-07-14) : `django-filter`.** L'approche idiomatique DRF pour ce besoin (`DjangoFilterBackend` + une `FilterSet`) : déclaratif, lisible, gère nativement les bornes de date (`lookup_expr` `lte`/`gte`) et le passage en 400 sur valeur invalide. Ajout à `requirements.txt` + `INSTALLED_APPS` (`django_filters`) + `DEFAULT_FILTER_BACKENDS` dans `REST_FRAMEWORK`.

## 6. Tests à couvrir

- Chaque filtre seul renvoie le bon sous-ensemble (`project`, `status`, `priority`, `due_date_before`, `due_date_after`).
- Combinaison de deux filtres (ET).
- Aucun paramètre → toutes les tâches de l'utilisateur (non-régression).
- `status`/`priority` invalide → 400 ; `due_date_before`/`due_date_after` mal formée → 400.
- `project` d'un autre utilisateur → `[]` (et **jamais** les tâches de l'autre).
- `project` **inexistant** → `[]`, **identique** au cas « projet d'autrui » (pas d'oracle 400 vs 200).
- `project` non numérique → 400.
- Un filtre ne fait jamais apparaître une tâche hors du périmètre de l'utilisateur (isolation préservée).

## 7. Hors scope

- **Tri** (`ordering`) et **pagination** : non traités ici.
- **Recherche plein-texte** sur `title`/`description` : non demandée en V1.
- **Filtres sur les projets** : hors périmètre.
- **Tableau de bord** (composition des vues « en retard / à venir / par statut », calcul de la date du jour) : fonctionnalité distincte, sa propre spec.
- V2 / collaboratif.
