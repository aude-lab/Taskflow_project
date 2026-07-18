# SPEC — Ressource Task

## 1. Objectif

Permettre à l'utilisateur connecté de gérer (créer, lister, consulter, modifier, supprimer) les tâches rattachées à ses propres projets, avec un statut, une priorité et une échéance.

## 2. Modèle de données

| Champ | Type | Obligatoire | Contraintes |
|-------|------|-------------|-------------|
| `title` | `CharField` | oui | `max_length=200`, non vide |
| `description` | `TextField` | non | vide autorisé (`blank=True`) |
| `status` | `CharField` | non (défaut) | `choices=Status`, `max_length=20`, défaut `a_faire` |
| `priority` | `CharField` | non (défaut) | `choices=Priority`, `max_length=20`, défaut `moyenne` |
| `due_date` | `DateField` | non | `null=True, blank=True` ; **une date passée est autorisée** (c'est ce qui rend une tâche « en retard » au tableau de bord) |
| `project` | `ForeignKey → projects.Project` | oui | `on_delete=CASCADE`, `related_name='tasks'` ; **doit appartenir à l'utilisateur courant** (garanti par un queryset restreint, cf. ci-dessous) |
| `created_at` | `DateTimeField` | auto | `auto_now_add=True` (lecture seule) |
| `updated_at` | `DateTimeField` | auto | `auto_now=True` (lecture seule) |

**Choices** (valeurs stockées en ASCII sans accents, libellé accentué en affichage uniquement) :

```
Status   : a_faire → "À faire" | en_cours → "En cours" | termine → "Terminé"
Priority : basse → "Basse"     | moyenne → "Moyenne"   | haute → "Haute"
```

Définis en `TextChoices` sur le modèle — source de vérité unique, réutilisée par le serializer et les tests (jamais de valeur recopiée en dur).

- `Meta.ordering = ['-created_at']`.
- `__str__` retourne `title`.
- Champs exposés par le serializer (liste blanche, pas de `__all__`) : `id`, `title`, `description`, `status`, `priority`, `due_date`, `project`, `created_at`, `updated_at`.
- `read_only_fields` : `id`, `created_at`, `updated_at`.
- `project` est **écrivable** par le client (contrairement à `owner` de Project). Sa sécurité repose sur un **queryset restreint**, pas sur une validation manuelle : le `PrimaryKeyRelatedField` reçoit `Project.objects.filter(owner=request.user)` (l'utilisateur vient du contexte du serializer, fourni par le ViewSet).
  - Conséquence : un projet hors de ce queryset — inexistant **ou** appartenant à autrui — est rejeté par le mécanisme natif de DRF, avec le même `does_not_exist`. La fuite d'information devient **impossible par construction**, et non par une validation qu'on pourrait oublier ou mal calibrer.
  - Cela **retire le besoin d'écrire `validate_project()`** : aucune validation custom sur ce champ.
  - Bénéfice annexe : l'API browsable ne propose que les projets de l'utilisateur.

## 3. Endpoints exposés

Base : `/api/tasks/` (router DRF, `basename='task'`). Toutes les routes exigent un utilisateur authentifié et n'opèrent que sur les tâches de ses propres projets.

| Action | Méthode | URL | Succès | Corps réponse |
|--------|---------|-----|--------|---------------|
| list | GET | `/api/tasks/` | 200 | tableau JSON des tâches de l'utilisateur |
| create | POST | `/api/tasks/` | 201 | la tâche créée |
| retrieve | GET | `/api/tasks/{id}/` | 200 | la tâche |
| update | PUT | `/api/tasks/{id}/` | 200 | la tâche mise à jour |
| partial_update | PATCH | `/api/tasks/{id}/` | 200 | la tâche mise à jour |
| destroy | DELETE | `/api/tasks/{id}/` | 204 | corps vide |

Forme d'une tâche (JSON) :
```json
{
  "id": 1,
  "title": "Rédiger la maquette",
  "description": "",
  "status": "a_faire",
  "priority": "moyenne",
  "due_date": "2026-08-01",
  "project": 3,
  "created_at": "2026-07-14T10:00:00Z",
  "updated_at": "2026-07-14T10:00:00Z"
}
```

## 4. Règles de permission

- `permission_classes = [IsAuthenticated]`.
- `get_queryset()` filtre **toujours** via le projet parent :
  `Task.objects.filter(project__owner=self.request.user).select_related('project')`
  (le `select_related` évite les N+1 lors de la sérialisation de la liste).
- Pas de `perform_create` : l'appartenance découle du `project`, dont le queryset est restreint dans le serializer.
- Une tâche d'un autre utilisateur est **invisible** : retrieve/update/destroy → **404** (et non 403), car hors du queryset.
- Rattacher une tâche au projet d'un autre utilisateur est **impossible** : le projet est hors du queryset du champ, donc rejeté par le **mécanisme natif de DRF** (erreur `does_not_exist` → **400**). Aucune validation custom, aucun message d'erreur écrit à la main : c'est DRF qui produit la réponse, identique à celle d'un projet inexistant. Vaut aussi bien en create qu'en update/PATCH.

## 5. Cas limites à couvrir (tests)

- `title` vide/absent → **400**.
- `title` > 200 caractères → **400**.
- `project` absent → **400**.
- `project` inexistant → **400**.
- `project` appartenant à un autre utilisateur → **400** (ne doit pas permettre de rattacher une tâche au projet d'autrui).
- **Non-discernabilité** : « `project` d'un autre utilisateur » et « `project` inexistant » doivent produire **exactement le même corps de réponse**, pas seulement le même code 400. À tester par **égalité stricte** des deux réponses — en interrogeant le **même pk** dans les deux cas (créer un projet chez l'autre utilisateur, tenter le rattachement, supprimer ce projet, retenter avec le même pk), sinon la comparaison ne prouve rien. Sans ce test, une divergence de message rouvrirait la fuite sans que rien n'échoue.
- Déplacer (PATCH) une tâche vers le projet d'un autre utilisateur → **400**.
- `status` hors liste (ex. `"fini"`, `"terminé"` accentué) → **400**.
- `priority` hors liste → **400**.
- `status`/`priority` absents → **201** avec les valeurs par défaut (`a_faire`, `moyenne`).
- `description` absente → **201**, description vide.
- `due_date` absente → **201**, `due_date` à `null`.
- `due_date` mal formée (ex. `"01/08/2026"`) → **400**.
- `due_date` dans le passé → **201** (autorisé, cf. §2).
- Accès (GET/PUT/PATCH/DELETE) à une tâche d'un autre utilisateur → **404**.
- Liste : ne renvoie que les tâches des projets de l'utilisateur.
- Requête non authentifiée → **401**.
- Suppression d'un projet → ses tâches sont supprimées en cascade.

## 6. Hors scope

- **Filtres** (par projet, statut, priorité, échéance) et **tableau de bord** : fonctionnalités V1 à part entière, chacune sa propre spec.
- **Pagination** et tri configurable : non traités ici.
- **Collaboratif / V2** : pas de partage, d'assignation à un autre utilisateur, ni de rôle. Une tâche appartient à l'unique propriétaire de son projet.
- Modification de la ressource `Project` : hors périmètre (le `related_name='tasks'` est ajouté côté `Task`, sans toucher `projects/`).
