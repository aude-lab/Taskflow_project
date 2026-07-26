# SPEC — Front, tranche 4 : tableau de bord

## 1. Objectif

Transformer la page d'accueil (aujourd'hui un placeholder) en tableau de bord : les tâches en retard, celles à venir (14 jours), et la répartition par statut — pour l'utilisateur connecté.

## 2. Périmètre

**Inclus** : la page `/` (`HomeView`) affiche les trois catégories, en lecture seule.

**Exclu** : aucun nouvel endpoint, aucun filtre configurable (les fenêtres sont fixes, comme l'API), pas de graphique. Les filtres avancés restent la tranche 5.

## 3. Architecture — source unique de la logique dashboard

Les définitions des catégories existent déjà dans l'API `tasks/views.py::DashboardView` (`tasks/SPEC-dashboard.md`) : `overdue = due_date < aujourd'hui ET status != termine`, `upcoming = [aujourd'hui, aujourd'hui+14] ET status != termine`, `by_status` = compteur par statut, `aujourd'hui = timezone.localdate()`, base = `Task.objects.for_user(user)`.

**Le front ne réimplémente pas ces règles.** On **extrait** la logique dans une fonction partagée :

```
tasks/dashboard.py
    build_dashboard(user) -> {
        "overdue":  QuerySet[Task],
        "upcoming": QuerySet[Task],
        "by_status": {a_faire: int, en_cours: int, termine: int},
    }
```

- Elle encapsule le calcul de `aujourd'hui` (serveur), les fenêtres de dates (via `TaskFilter`, comme aujourd'hui), l'exclusion des terminées, et l'agrégation `by_status` — **exactement** la logique actuelle de l'API.
- **`DashboardView` (API) est réécrite pour l'appeler** : elle ne fait plus que sérialiser le résultat (`{count, tasks}` + `by_status`). C'est un refactoring à comportement constant : **les 11 tests API dashboard doivent passer sans modification** (même preuve de non-régression que pour `core/queries` → managers).
- **`HomeView` (front) l'appelle aussi** et passe les querysets/compteurs au template.

Elle prend un `user` (pas une `request`), cohérente avec `for_user()`.

## 4. Où vit la vue front — décision à valider

`HomeView` est aujourd'hui dans `core/views_web.py`. Deux options :

- **(a) La garder dans `core`**, en important `build_dashboard` depuis `tasks`. Simple (l'accueil `/` reste servi par `core`), mais `core/views_web.py` dépend alors de `tasks`. **Acceptable** : c'est une *vue* (sommet de la pile, comme `taskflow/urls.py` qui importe déjà toutes les apps), pas un utilitaire-feuille réutilisé ailleurs — aucun cycle d'import (`tasks` n'importe pas `core.views_web`). **Recommandé.**
- (b) Déplacer la vue d'accueil dans `tasks/views_web.py` et n'y laisser qu'un routage. Évite toute dépendance `core → tasks`, mais éclate l'accueil `/` entre deux apps.

Recommandation : **(a)**. À trancher par Aude ; ce spec suppose (a).

## 5. Contenu de la page

Trois sections, chacune avec un titre et un compteur :

- **En retard** — liste des tâches `overdue` : titre (→ lien vers sa page d'édition), projet, priorité, échéance. Mises en évidence (ex. bordure/badge rouge). État vide : « Aucune tâche en retard. »
- **À venir (14 jours)** — même présentation, état vide explicite.
- **Par statut** — les trois compteurs (`À faire`, `En cours`, `Terminé`), en cartes ou badges, via les libellés du modèle (`get_status_display`), pas les valeurs ASCII.

Chaque tâche renvoie vers son projet ou son édition (liens déjà existants de la tranche 3). L'ordre des listes est celui du modèle (`-created_at`).

## 6. Sécurité

- **`LoginRequiredMixin` sur `HomeView`** (déjà présent).
- La base est `Task.objects.for_user(user)` **dans `build_dashboard`** : aucune tâche d'autrui ne peut apparaître ni être comptée.
- **`aujourd'hui` calculé côté serveur** (`timezone.localdate()`), dans `build_dashboard`, indépendant de toute entrée client.
- Pas d'écriture, pas de formulaire → pas de surface CSRF nouvelle.

## 7. Cas limites à couvrir (tests)

L'API teste déjà finement les bornes (j+14 inclus, j non en retard, null exclu…). Côté front, on teste ce que la page **rend**, sans redupliquer toute la matrice :

- **Aucune tâche** → les deux listes affichent leur état vide, les compteurs `by_status` sont à 0.
- **Une tâche en retard non terminée** → apparaît dans « En retard », pas dans « À venir ».
- **Une tâche en retard mais terminée** → n'apparaît **pas** dans « En retard ».
- **Une tâche à échéance dans 7 jours** → apparaît dans « À venir ».
- **Isolation** : les tâches d'un autre utilisateur (en retard, à venir, tous statuts) **n'apparaissent jamais** ni ne sont comptées.
- **Anonyme sur `/`** → **302** vers la connexion (jamais 500).
- `by_status` : la page affiche le bon compteur par statut (libellés accentués).

**Non-régression** : la réécriture de `DashboardView` autour de `build_dashboard` ne change aucun comportement de l'API → **les 11 tests API dashboard passent sans être modifiés** (vérifié par checksum/diff, comme pour les refactorings précédents). Suite complète toujours verte.

## 8. Hors scope

- Filtres configurables sur le dashboard (tranche 5).
- Nouvel endpoint API ou changement de la forme de la réponse `/api/dashboard/`.
- Pagination des listes (V1 suppose un volume raisonnable, cf. `tasks/SPEC-dashboard.md`).
- Graphiques, tri personnalisé, personnalisation de la fenêtre « à venir ».
- V2 / collaboratif.
