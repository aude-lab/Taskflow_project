# SPEC — Règle d'appartenance partagée (« qui voit quoi »)

## 1. Objectif

Faire vivre la règle « qui peut voir quoi » à **un seul endroit par modèle**, pour que les ViewSets DRF, les serializers et les **futures vues front (Django classique + session)** s'appuient tous dessus. Deux implémentations séparées de cette règle finiraient par diverger — et une divergence ici est une faille d'isolation.

## 2. Où vit la règle : des managers custom, par app

Chaque modèle porte sa propre règle d'appartenance, dans l'app qui le possède :

| Fichier | Déclaration | Expression |
|---------|-------------|------------|
| `projects/models.py` | `ProjectQuerySet.for_user(user)`, exposé via `objects = ProjectQuerySet.as_manager()` | `self.filter(owner=user)` |
| `tasks/models.py` | `TaskQuerySet.for_user(user)`, exposé via `objects = TaskQuerySet.as_manager()` | `self.filter(project__owner=user).select_related("project")` |

Usage : `Project.objects.for_user(user)` et `Task.objects.for_user(user)`.

**Pourquoi des managers plutôt qu'un module `core/queries.py`** (choix acté après review) :
- **Pas de couplage inversé.** Un module `core` qui importe `projects.models` et `tasks.models` fait dépendre la brique partagée des apps métier, alors que `core` est censé être la feuille du graphe. Le graphe restait acyclique par chance ; le jour où un `models.py` aurait importé `core`, c'était un `ImportError` au démarrage.
- **« Une app = une responsabilité »** (CLAUDE.md) : la règle vit dans l'app qui possède le modèle.
- **Accessible partout sans import supplémentaire** : les serializers, qui manipulent déjà le modèle, y accèdent naturellement — c'est ce qui a permis de rallier les deux sites du chemin d'écriture.
- **Chaînable** : `as_manager()` construit une classe de `Manager` dérivée du QuerySet, dont `get_queryset()` renvoie ce QuerySet — donc `.filter()`, `.exclude()`, `.values()` continuent de fonctionner derrière `for_user()`.

Précisions :
- Ces méthodes prennent un **`user`**, pas une `request` : utilisables depuis un ViewSet DRF comme depuis une vue Django classique.
- Le `select_related("project")` est **inclus** dans `Task.objects.for_user`, car tous les appelants l'appliquaient déjà : le conserver garantit un comportement et un nombre de requêtes strictement identiques.
- Elles **supposent un utilisateur authentifié** : l'authentification reste la responsabilité de l'appelant (`IsAuthenticated` côté DRF ; `LoginRequiredMixin` côté front à venir). Aucun garde n'est ajouté — en ajouter changerait le comportement, hors périmètre d'un refactoring.

## 3. Les 5 sites ralliés

Toute la duplication de la règle d'appartenance a disparu :

| Fichier | Site | Utilise désormais |
|---------|------|-------------------|
| `projects/views.py` | `ProjectViewSet.get_queryset()` | `Project.objects.for_user(user)` |
| `tasks/views.py` | `TaskViewSet.get_queryset()` | `Task.objects.for_user(user)` |
| `tasks/views.py` | `DashboardView.base_queryset()` | `Task.objects.for_user(user)` |
| `tasks/serializers.py` | `get_fields()` — restriction de la FK `project` | `Project.objects.for_user(user)` |
| `projects/serializers.py` | `validate_name()` — unicité par propriétaire | `Project.objects.for_user(user).filter(name=value)` |

Les trois premiers relèvent du **chemin de lecture**, les deux derniers du **chemin d'écriture** — précisément la famille de bugs décrite dans la section « Principe général » du skill `drf-resource`. Les deux chemins partagent maintenant la même source, donc ne peuvent plus diverger.

`core/queries.py` (étape intermédiaire de ce refactoring) est **supprimé** : `core` ne dépend plus d'aucune app métier.

## 4. Aucun changement de comportement observable

**Refactoring pur**, pas une fonctionnalité :

- Mêmes résultats (mêmes objets, même `ordering`, même `select_related`), même SQL.
- Mêmes permissions et mêmes codes de réponse (404 pour l'objet d'autrui, 401 non authentifié, 400 sur unicité…).
- Mêmes corps de réponse JSON. Le dashboard reste à 3 requêtes.
- **Aucune migration** : les managers ne sont pas sérialisés (`use_in_migrations` reste à `False`), vérifié par `makemigrations --check` → *No changes detected*.
- Aucune modification de modèle (champs), de serializer (champs exposés), de filtre ni d'URL.
- Effets de bord du changement de manager par défaut : vérifiés nuls. Le related manager (`project.tasks`) et l'admin produisent le même SQL qu'avant — le `select_related` de `for_user()` ne fuit pas dans le related manager, `_base_manager` reste inchangé (FK, cascades).

> **À savoir** : `for_user()` est aussi exposé sur le related manager, donc `project.tasks.for_user(u)` existe. L'appeler appliquerait un second filtre d'appartenance redondant. Inoffensif, mais sans intérêt : partir de `Task.objects.for_user(u)`.

## 5. Tests

**La suite existante passe sans aucune modification** — c'est la preuve de non-régression : `accounts/tests.py`, `projects/tests.py`, `tasks/tests.py` sont inchangés (checksums md5 identiques avant/après, `git diff -- '*tests.py'` vide).

**Règle stricte** : si un seul test devait être modifié pour passer, c'est le refactoring qui serait à corriger, jamais le test. Aucun test n'est ajouté ni supprimé : `for_user()` n'introduit aucun comportement propre, il est intégralement couvert par les tests d'isolation existants (utilisateur B ne voit pas les données de A), qui passent désormais par lui.

## 6. Hors scope

- Aucune vue front (ce refactoring **prépare** le front, il ne le commence pas).
- Aucune méthode de manager « au cas où » : uniquement `for_user()`, réellement utilisée.
- Aucun changement de permission, de garde d'authentification, ni d'optimisation de requête.
- V2 / collaboratif.
