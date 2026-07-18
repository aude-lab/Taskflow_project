# SPEC — Ressource Project

## 1. Objectif

Permettre à l'utilisateur connecté de gérer (créer, lister, consulter, modifier, supprimer) ses propres projets, qui serviront de conteneurs aux tâches.

## 2. Modèle de données

| Champ | Type | Obligatoire | Contraintes |
|-------|------|-------------|-------------|
| `name` | `CharField` | oui | `max_length=200`, non vide |
| `description` | `TextField` | non | vide autorisé (`blank=True`) |
| `owner` | `ForeignKey → accounts.User` | oui | `on_delete=CASCADE` ; **fixé côté serveur** (jamais envoyé par le client) |
| `created_at` | `DateTimeField` | auto | `auto_now_add=True` (lecture seule) |
| `updated_at` | `DateTimeField` | auto | `auto_now=True` (lecture seule) |

- `Meta.ordering = ['-created_at']` (liste stable, plus récents d'abord).
- `Meta.unique_together = [['owner', 'name']]` : deux projets d'une même utilisatrice ne peuvent pas porter le même `name` (unicité par utilisateur, pas globale).
- `__str__` retourne `name`.
- Champs exposés par le serializer (liste blanche, pas de `__all__`) : `id`, `name`, `description`, `created_at`, `updated_at`.
- `read_only_fields` : `id`, `created_at`, `updated_at`. `owner` n'est pas exposé en écriture (rempli via `perform_create`).

## 3. Endpoints exposés

Base : `/api/projects/` (router DRF, `basename='project'`). Toutes les routes exigent un utilisateur authentifié et n'opèrent que sur ses projets.

| Action | Méthode | URL | Succès | Corps réponse |
|--------|---------|-----|--------|---------------|
| list | GET | `/api/projects/` | 200 | tableau JSON des projets de l'utilisateur |
| create | POST | `/api/projects/` | 201 | le projet créé |
| retrieve | GET | `/api/projects/{id}/` | 200 | le projet |
| update | PUT | `/api/projects/{id}/` | 200 | le projet mis à jour |
| partial_update | PATCH | `/api/projects/{id}/` | 200 | le projet mis à jour |
| destroy | DELETE | `/api/projects/{id}/` | 204 | corps vide |

Forme d'un projet (JSON) :
```json
{
  "id": 1,
  "name": "Refonte site",
  "description": "",
  "created_at": "2026-07-13T10:00:00Z",
  "updated_at": "2026-07-13T10:00:00Z"
}
```

## 4. Règles de permission

- `permission_classes = [IsAuthenticated]`.
- `get_queryset()` filtre **toujours** : `Project.objects.filter(owner=self.request.user)`.
- `perform_create()` fixe l'owner : `serializer.save(owner=self.request.user)`.
- Un projet appartenant à un autre utilisateur est **invisible** : accès en retrieve/update/destroy → **404** (et non 403), car l'objet est hors du queryset. On ne révèle pas son existence.

## 5. Cas limites à couvrir (tests)

- `name` vide/absent → **400**.
- `name` > 200 caractères → **400**.
- `name` déjà utilisé par un autre projet de la **même** utilisatrice → **400** (le même `name` reste autorisé chez une autre utilisatrice).
- `description` absente → **201**, projet créé avec description vide.
- Accès (GET/PUT/PATCH/DELETE) à un projet d'un autre utilisateur → **404**.
- `owner` envoyé dans le corps de la requête → **ignoré**, l'owner reste l'utilisateur courant.
- Requête non authentifiée → **401**.

## 6. Hors scope

- **Task** : aucun champ, endpoint ou logique liée aux tâches ici (ressource séparée, sa propre spec).
- **Collaboratif / V2** : pas de partage, pas de rôle owner/membre, pas d'invitation. Un projet a un unique propriétaire.
- Pagination, filtres et tri avancés : non traités dans cette spec (au besoin, spec dédiée).
