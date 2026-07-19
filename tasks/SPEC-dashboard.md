# SPEC — Tableau de bord

## 1. Objectif

Fournir à l'utilisateur connecté une vue d'ensemble de ses tâches : ce qui est en retard, ce qui arrive, et la répartition par statut — sous forme de **compteurs + listes** des tâches concernées.

## 2. Endpoint

| Méthode | URL | Permission |
|---------|-----|------------|
| GET | `/api/dashboard/` | `IsAuthenticated` |

Action unique en lecture seule, donc **pas de ViewSet ni de router** : une `APIView` (ou `GenericAPIView`) dans `tasks/views.py`, câblée par un `path()` explicite dans `tasks/urls.py`. Aucune écriture.

## 3. Catégories exposées

Toutes calculées sur **l'ensemble des tâches de l'utilisateur** (voir §5). `aujourd'hui` = date du serveur (voir §5), jamais fournie par le client.

| Catégorie | Définition | Contenu |
|-----------|------------|---------|
| `overdue` (en retard) | `due_date < aujourd'hui` **ET** `status != termine` | compteur + liste |
| `upcoming` (à venir) | `aujourd'hui <= due_date <= aujourd'hui + 14 jours` **ET** `status != termine` | compteur + liste |
| `by_status` (par statut) | compteur par valeur de `Status`, sur **toutes** les tâches de l'utilisateur | compteurs seuls |

**Bornes tranchées explicitement :**
- Une tâche dont `due_date == aujourd'hui` est **à venir**, pas en retard (`overdue` est strictement `< aujourd'hui`).
- Une tâche dont `due_date == aujourd'hui + 14 jours` **est incluse** dans `upcoming` (borne haute **inclusive**). La fenêtre est donc `[aujourd'hui, aujourd'hui + 14]`, bornes comprises.
- Les tâches sans `due_date` (`null`) n'apparaissent ni dans `overdue` ni dans `upcoming` (une tâche sans échéance n'est ni en retard ni imminente). Elles restent comptées dans `by_status`.

**Réutilisation des filtres existants (pas de duplication de requête).** Les fenêtres de dates s'appuient sur `TaskFilter` (`tasks/filters.py`), appliqué sur le queryset de base :
- `upcoming` : `due_date_after = aujourd'hui`, `due_date_before = aujourd'hui + 14 jours`.
- `overdue` : `due_date_before = aujourd'hui - 1 jour` (équivaut à `< aujourd'hui`, la borne du filtre étant `lte`).
- L'exclusion `status != termine` est propre au dashboard (le filtre `status` est un égal, pas un « différent ») : appliquée en plus, via `.exclude(status=Task.Status.DONE)`.
- `by_status` : agrégation `values('status').annotate(count=Count('id'))` sur le queryset de base, complétée à zéro pour les statuts absents.

## 4. Forme de la réponse (200)

Chaque tâche des listes est sérialisée par le `TaskSerializer` existant (mêmes champs que `/api/tasks/`).

```json
{
  "overdue": {
    "count": 2,
    "tasks": [ { /* Task */ }, { /* Task */ } ]
  },
  "upcoming": {
    "count": 1,
    "tasks": [ { /* Task */ } ]
  },
  "by_status": {
    "a_faire": 5,
    "en_cours": 3,
    "termine": 4
  }
}
```

- `by_status` contient **toujours les trois clés** (valeurs de `Status`), à `0` si aucune tâche.
- `count` est redondant avec `len(tasks)` pour `overdue`/`upcoming`, mais exposé explicitement pour un usage direct côté client.

## 5. Sécurité

Reprend le **principe général** du skill `drf-resource` (valider/agréger contre le bon périmètre) :

- **Ensemble de départ = `Task.objects.for_user(request.user)`** (le même manager que `TaskViewSet.get_queryset`, cf. `tasks/SPEC.md` §7), **jamais** `Task.objects.all()`. Toutes les catégories dérivent de ce queryset : aucune tâche d'autrui ne peut apparaître ni être comptée. Passer par le manager plutôt que de réécrire le filtre garantit que le dashboard ne peut pas diverger de la règle appliquée ailleurs.
- **`aujourd'hui` est calculé côté serveur** via `django.utils.timezone.localdate()` (cohérent avec `TIME_ZONE`/`USE_TZ`). Il ne dépend d'**aucun paramètre de requête, en-tête ou corps** : le client ne peut pas décaler la fenêtre ni sonder d'autres dates.
- Requête non authentifiée → **401**.

## 6. Cas limites à couvrir (tests)

- **Aucune tâche en retard / à venir** → listes vides, `count = 0` (et non une erreur).
- **Tâche `due_date == aujourd'hui + 14 jours`** → **présente** dans `upcoming` (borne haute incluse).
- **Tâche `due_date == aujourd'hui`** → dans `upcoming`, **pas** dans `overdue`.
- **Tâche en retard mais `status == termine`** → **absente** d'`overdue` (une tâche terminée n'est pas en retard). Idem pour `upcoming`.
- **Tâche sans `due_date`** → absente d'`overdue`/`upcoming`, mais comptée dans `by_status`.
- **Utilisateur sans aucune tâche** → `overdue`/`upcoming` vides à 0, `by_status` = `{a_faire: 0, en_cours: 0, termine: 0}`.
- **Isolation** : les tâches (en retard, à venir, tous statuts) d'un autre utilisateur n'apparaissent ni ne sont comptées.
- **Requête non authentifiée** → 401.

## 7. Hors scope

- **Pagination des listes** : la V1 suppose un volume raisonnable de tâches par utilisateur ; les listes `overdue`/`upcoming` sont renvoyées entières.
- **Personnalisation de la fenêtre « à venir »** : 14 jours est fixe, non configurable par le client.
- **Tri** des listes au-delà de l'`ordering` par défaut du modèle (`-created_at`).
- **Filtres** combinés au dashboard (par projet, priorité…) : le dashboard est une vue agrégée fixe ; le filtrage fin reste sur `/api/tasks/`.
- V2 / collaboratif.
