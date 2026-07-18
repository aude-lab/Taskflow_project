# SPEC — Requêtes partagées (« qui voit quoi »)

## 1. Objectif

Extraire dans `core/` la logique de filtrage par utilisateur, aujourd'hui dupliquée dans les ViewSets, pour que les **futures vues front (Django classique + session)** et les **ViewSets DRF** partagent une **source de vérité unique**. Deux implémentations séparées de « qui peut voir quoi » finiraient par diverger — et une divergence sur cette règle est précisément une faille d'isolation.

## 2. Fonctions à extraire

Emplacement : **`core/queries.py`** (nouveau fichier).

```
get_user_projects(user)  ->  QuerySet[Project]
get_user_tasks(user)     ->  QuerySet[Task]
```

- `get_user_projects(user)` : `Project.objects.filter(owner=user)`
- `get_user_tasks(user)` : `Task.objects.filter(project__owner=user).select_related("project")`

Précisions :
- Elles prennent un **`user`**, pas une `request` : utilisables aussi bien depuis un ViewSet DRF que depuis une vue Django classique.
- Le `select_related("project")` est **inclus** dans `get_user_tasks`, car les deux appelants actuels l'appliquent déjà : le conserver garantit un comportement (et un nombre de requêtes) strictement identique.
- Elles renvoient un **QuerySet** (paresseux, chaînable) : les appelants peuvent continuer à `.filter()`, `.exclude()`, `.values()` dessus comme aujourd'hui.
- Elles **supposent un utilisateur authentifié**, comme aujourd'hui : l'authentification reste la responsabilité de l'appelant (`IsAuthenticated` côté DRF). Aucun garde n'est ajouté — en ajouter changerait le comportement, ce qui sort du périmètre de ce refactoring.

## 3. Appelants modifiés

| Fichier | Avant | Après |
|---------|-------|-------|
| `projects/views.py` | `ProjectViewSet.get_queryset()` : `Project.objects.filter(owner=self.request.user)` | `return get_user_projects(self.request.user)` |
| `tasks/views.py` | `TaskViewSet.get_queryset()` : `Task.objects.filter(project__owner=self.request.user).select_related("project")` | `return get_user_tasks(self.request.user)` |
| `tasks/views.py` | `DashboardView.base_queryset()` : même expression dupliquée | `return get_user_tasks(self.request.user)` |

Ces trois sites dupliquent aujourd'hui la même règle ; après refactoring, ils partagent la même source.

**Reste à faire (hors périmètre de ce refactoring)** — deux autres sites appliquent la même règle et ne sont **pas** couverts ici :

| Site | Expression | Équivalent |
|------|-----------|------------|
| `tasks/serializers.py` (`get_fields`) | `Project.objects.filter(owner=self.context["request"].user)` | `get_user_projects(user)` |
| `projects/serializers.py` (`validate_name`) | `Project.objects.filter(owner=user, name=value)` | `get_user_projects(user).filter(name=value)` |

Ce sont les sites du **chemin d'écriture** (restriction de la FK, validation d'unicité) — précisément la famille de bugs décrite dans la section « Principe général » du skill `drf-resource`. Tant qu'ils ne sont pas ralliés, la règle « qui voit quoi » vit à **deux** endroits (lecture / écriture) et peut diverger. À traiter dans une passe dédiée, décision d'Aude.

## 4. Aucun changement de comportement observable

C'est un **refactoring pur**, pas une fonctionnalité :

- Mêmes résultats (mêmes objets, même `ordering`, même `select_related`).
- Mêmes permissions et mêmes codes de réponse (404 pour l'objet d'autrui, 401 non authentifié, etc.).
- Mêmes corps de réponse JSON.
- Même nombre de requêtes SQL (le dashboard reste à 3).
- Aucune modification de modèle, de migration, de serializer, de filtre ni d'URL.

## 5. Tests

**La suite existante doit passer sans aucune modification** — c'est la preuve de non-régression :

- `projects/tests.py` (CRUD Project, isolation)
- `tasks/tests.py` (CRUD Task, filtres, dashboard)
- `accounts/tests.py` (inscription)

**Règle stricte** : si un seul test devait être modifié pour passer, cela signifierait que le refactoring a altéré un comportement — le refactoring serait alors à corriger, jamais le test. Aucun test n'est ajouté ni supprimé : `core/queries.py` n'introduit aucun comportement propre à tester, il est intégralement couvert par les tests d'isolation existants (utilisateur B ne voit pas les données de A) qui passent désormais par lui.

## 6. Hors scope

- Aucune vue front (le refactoring **prépare** le front, il ne le commence pas).
- Aucun nouveau helper « au cas où » : uniquement les deux fonctions réellement utilisées par les appelants existants.
- Aucun changement de permission, de garde d'authentification, ni d'optimisation de requête.
- V2 / collaboratif.
