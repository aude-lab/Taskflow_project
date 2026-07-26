# SPEC — Front, tranche 5 : liste des tâches filtrable

## 1. Objectif

Offrir une page qui liste **toutes les tâches de l'utilisateur** (tous projets confondus) avec des filtres : par projet, statut, priorité et échéance. C'est la dernière brique fonctionnelle de la V1.

## 2. Périmètre

**Inclus** : une page `/taches/` listant les tâches filtrées, un formulaire de filtres (GET), un lien « Tâches » dans la navigation.

**Exclu** : pagination, tri configurable, recherche plein-texte, filtres sauvegardés. La liste par projet (page de détail projet) et le dashboard restent tels quels.

## 3. Architecture

| Élément | Emplacement |
|---------|-------------|
| Vue | `tasks/views_web.py` → `TaskListView` |
| URL | `tasks/urls_web.py` → `/taches/`, nom `task_list` |
| Template | `tasks/templates/tasks/task_list.html` |
| Lien nav | `core/templates/base.html` |

`ListView` + `LoginRequiredMixin`.

**Réutilisation de `TaskFilter` (source unique du filtrage), sans le modifier.** La logique de filtrage (statut, priorité, projet, bornes de date) vit déjà dans `tasks/filters.py::TaskFilter`, utilisée par l'API et le dashboard. La vue front l'applique sur le queryset de base :

```
TaskFilter(request.GET, queryset=Task.objects.for_user(request.user), request=request).qs
```

- **`TaskFilter` n'est pas modifié** : l'API en dépend (ses tests figent le comportement, dont `project` en `NumberFilter` pour éviter l'oracle d'existence — cf. `tasks/SPEC-filters.md` §4). Le front réutilise **exactement** ce comportement.
- Les **noms de paramètres GET** du formulaire front correspondent à ceux de `TaskFilter` : `project`, `status`, `priority`, `due_date_after`, `due_date_before`.

## 4. Formulaire de filtres (présentation front)

Rendu **par le front** (le template), pas par le formulaire auto de django-filter, pour une meilleure UX. Formulaire en **GET** (les filtres doivent être partageables/rechargeables via l'URL) :

| Champ | Contrôle | Alimenté par |
|-------|----------|--------------|
| Projet | `<select>` | **les projets de l'utilisateur** (`Project.objects.for_user(user)`), option « Tous » vide. `value` = pk. |
| Statut | `<select>` | `Task.Status.choices`, option « Tous » vide. |
| Priorité | `<select>` | `Task.Priority.choices`, option « Tous » vide. |
| Échéance à partir du | `<input type="date">` | `due_date_after` |
| Échéance jusqu'au | `<input type="date">` | `due_date_before` |

- Le `<select>` projet ne liste **que les projets de l'utilisateur** : il ne peut pas proposer le projet d'autrui. Sa `value` est un pk soumis au paramètre `project`, traité par le `NumberFilter` de `TaskFilter` (comportement identique à l'API).
- Les valeurs sélectionnées doivent **persister** dans le formulaire après soumission (le formulaire reflète les filtres actifs lus depuis `request.GET`).
- Un bouton « Filtrer » et un lien « Réinitialiser » (vers `/taches/` sans paramètre).

## 5. Sécurité

- **`LoginRequiredMixin`** sur la vue.
- **Base = `Task.objects.for_user(user)`** : les filtres s'appliquent **après**, ils ne peuvent que réduire. Aucune tâche d'autrui ne peut apparaître, quel que soit le filtre.
- Le `<select>` projet n'expose que `for_user(user)` → l'utilisateur ne peut pas choisir le projet d'autrui dans l'UI. Et un `project=<pk d'autrui>` **forgé dans l'URL** ne renvoie **rien** (le `NumberFilter` filtre un queryset déjà restreint → intersection vide), jamais les tâches de l'autre, jamais d'erreur révélant l'existence du projet.
- Aucune écriture, aucun formulaire POST → pas de surface CSRF nouvelle.

## 6. Contenu de la page

- **Liste** : pour chaque tâche — titre (→ lien vers son édition), projet, statut, priorité, échéance. Ordre du modèle (`-created_at`).
- **État vide** : distinguer « aucune tâche » (l'utilisateur n'en a pas) de « aucun résultat pour ces filtres » — message explicite dans les deux cas.
- **Filtres actifs visibles** : le formulaire reflète les filtres appliqués ; un compteur de résultats est un plus.
- Pas de N+1 : le `select_related('project')` de `for_user` couvre l'accès à `task.project` dans la liste.

## 7. Comportement des valeurs invalides (décidé après validation spécialiste)

Vérifié empiriquement : `TaskFilter` utilisé **directement dans une vue** (hors `DjangoFilterBackend`) ne lève **jamais** d'exception sur une valeur invalide. En interne, `.qs` valide le formulaire du filtre et n'applique que les critères présents dans `cleaned_data` ; un champ invalide en est retiré → **son filtre est simplement ignoré**, les autres filtres valides s'appliquent, et la base `for_user(user)` reste toujours dans la requête.

**Décision V1** : la vue renvoie `filterset.qs` tel quel. Une valeur invalide dans une URL forgée (`status=bidon`, `due_date_before=pas-une-date`, `project=abc`) est **silencieusement ignorée** → page en **200**, périmètre non filtré sur ce seul critère. On **ne reproduit pas** le 400 de l'API : c'est une page HTML pour humain (selects fermés → cas quasi inatteignable hors URL forgée), pas le contrat d'API. Aucune fuite possible (l'isolation `for_user` est intacte), jamais de 500.

> Divergence assumée avec l'API : `project=abc` renvoie **200** (filtre ignoré) côté front, vs **400** côté API. C'est voulu — deux surfaces, deux contrats.

## 8. Cas limites à couvrir (tests)

- Aucun filtre → toutes les tâches de l'utilisateur.
- Chaque filtre seul (`project`, `status`, `priority`, `due_date_after`, `due_date_before`) → bon sous-ensemble.
- Combinaison de deux filtres → intersection (ET).
- Le `<select>` projet **ne contient que les projets de l'utilisateur** (pas ceux d'autrui) — vérifié dans le HTML.
- `project=<pk d'autrui>` forgé dans l'URL → **liste vide**, jamais les tâches de l'autre.
- Isolation générale : aucun filtre ne fait apparaître une tâche d'un autre utilisateur.
- Valeur invalide (`status` bidon, date malformée) dans l'URL → **pas de 500** (comportement fixé au plan).
- Persistance : après soumission, le formulaire ré-affiche les valeurs choisies.
- Anonyme sur `/taches/` → **302** vers la connexion.
- Performance : nombre de requêtes constant vs nombre de tâches (`assertNumQueries`).
- Non-régression : les 162 tests existants passent.

## 9. Hors scope

- Pagination, tri, recherche plein-texte, filtres enregistrés.
- Modification de `TaskFilter` (l'API en dépend) ou de son comportement.
- Actions groupées depuis la liste.
- V2 / collaboratif.
