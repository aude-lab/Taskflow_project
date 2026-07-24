# SPEC — Front, tranche 3 : CRUD tâches

## 1. Objectif

Permettre à l'utilisateur connecté de gérer les tâches d'un de ses projets depuis l'interface web : les lister (dans la page du projet), en créer, les modifier, les supprimer.

## 2. Périmètre

**Inclus** : la liste des tâches sur la page de détail d'un projet (elle remplace le placeholder de la tranche 2), et les pages création / modification / suppression d'une tâche.

**Exclu, tranches suivantes** : le tableau de bord (tranche 4), les filtres sur les tâches (tranche 5). Pas de page de détail de tâche isolée : la liste dans le projet + le formulaire d'édition suffisent.

## 3. Architecture

| Élément | Emplacement |
|---------|-------------|
| Vues | `tasks/views_web.py` |
| Formulaire | `tasks/forms.py` → `TaskForm` |
| URLs | `tasks/urls_web.py`, inclus à la racine |
| Templates | `tasks/templates/tasks/` |
| Liste des tâches | intégrée à `projects/templates/projects/project_detail.html` |

Vues génériques Django (`CreateView`, `UpdateView`, `DeleteView`), toutes avec `LoginRequiredMixin`. La liste est rendue par `ProjectDetailView` (tranche 2), enrichie ici.

## 4. Pages et URLs

Le projet parent est **porté par l'URL** en création ; il n'est donc pas un champ du formulaire (voir §6).

| URL | Vue | Rôle |
|-----|-----|------|
| `/projets/<project_pk>/taches/nouvelle/` | `TaskCreateView` | Créer une tâche dans ce projet |
| `/taches/<pk>/modifier/` | `TaskUpdateView` | Modifier une tâche |
| `/taches/<pk>/supprimer/` | `TaskDeleteView` | Confirmer puis supprimer (**POST**) |

Après création / modification / suppression : redirection vers la **page de détail du projet** parent, avec un message de succès.

## 5. Sécurité

Applique le **principe général** du skill `drf-resource`, comme l'API et la tranche 2 :

- **`LoginRequiredMixin` sur les trois vues.**
- **Les tâches manipulées passent par `Task.objects.for_user(self.request.user)`** : une tâche d'un autre utilisateur → **404** en modification / suppression.
- **En création, le projet parent est chargé via `Project.objects.for_user(user)`** (pk dans l'URL) : créer une tâche dans le projet d'autrui → **404**, on ne révèle pas son existence. Le projet n'est jamais pris depuis le POST.
- `{% csrf_token %}` sur tous les formulaires, y compris la suppression.

## 6. Formulaire (`TaskForm`)

`ModelForm` sur `Task`, champs **`title`, `description`, `status`, `priority`, `due_date`** — **`project` n'est pas un champ du formulaire** : il vient de l'URL en création, et reste inchangé en modification (voir §9, hors scope). `BootstrapFormMixin` pour le style.

- `status` et `priority` : rendus en `<select>`, alimentés par les `choices` du modèle (valeurs ASCII, libellés accentués — cf. `tasks/SPEC.md`). Aucune valeur recopiée à la main. **Ces champs sont obligatoires** (un `ModelForm` sur des champs à `choices` non `blank` les rend requis, sans option vide) ; le `<select>` **pré-sélectionne** le défaut du modèle (`a_faire` / `moyenne`), qu'un navigateur soumet toujours. « Défaut » signifie donc « pré-sélectionné », pas « appliqué en cas d'absence » : un POST qui omettrait le champ est une **erreur de formulaire**, pas un défaut silencieux (qui enregistrerait une valeur vide).
- `due_date` : **facultatif**, saisi via un `<input type="date">` HTML5. Le champ est **déclaré explicitement** dans le formulaire pour porter trois réglages indissociables :
  - `required=False` (le déclarer fait perdre l'héritage `blank=True` du modèle) ;
  - `input_formats=["%Y-%m-%d"]` (le format soumis par un `<input type="date">`) ;
  - **`widget=DateInput(attrs={"type": "date"}, format="%Y-%m-%d")`**.
  > **Point de vigilance — format de date, en entrée ET en sortie.** `LANGUAGE_CODE = 'fr-fr'` rend `JJ/MM/AAAA` prioritaire dans `DATE_INPUT_FORMATS`. Deux effets :
  > 1. **Entrée** : un `<input type="date">` soumet `AAAA-MM-JJ` ; `%Y-%m-%d` est certes déjà accepté par la locale `fr`, mais on le fixe explicitement pour ne pas dépendre de la locale.
  > 2. **Sortie (le vrai piège)** : **sans `format="%Y-%m-%d"` sur le widget**, une valeur existante se ré-affiche en `JJ/MM/AAAA` → **invalide pour un `<input type="date">`, qui s'ouvre alors VIDE** sur une tâche datée (l'utilisateur peut effacer la date sans le vouloir). Deux tests : un qui soumet `AAAA-MM-JJ` et vérifie l'enregistrement, un qui ouvre l'édition d'une tâche datée et vérifie que le HTML contient `value="AAAA-MM-JJ"`.
- Une échéance dans le passé reste **autorisée** (cohérent avec `tasks/SPEC.md` : c'est ce qui rend une tâche « en retard »).

## 7. Contenu des pages

- **Liste (dans le détail du projet)** : pour chaque tâche — titre, statut, priorité, échéance ; liens modifier / supprimer. Bouton « Nouvelle tâche ». État vide explicite si le projet n'a aucune tâche. Ordre : celui du modèle (`-created_at`).
  - Les tâches sont déjà chargées via le projet ; la liste ne doit pas déclencher de requête par tâche (pas de N+1). Un test `assertNumQueries` le garantit.
- **Création / modification** : même template de formulaire, titre adapté, `<select>` pour statut et priorité, sélecteur de date.
- **Suppression** : page de confirmation (titre de la tâche + projet parent), action irréversible.

## 8. Cas limites à couvrir (tests)

**Isolation**
- Créer une tâche dans le projet d'un autre utilisateur (`/projets/<pk d'autrui>/taches/nouvelle/`) → **404**, aucune tâche créée.
- Modifier / supprimer une tâche d'un autre utilisateur → **404** (GET **et** POST).
- Anonyme sur chacune des trois URLs → **302** vers la connexion (jamais 500), aucune écriture.

**Création / modification**
- Création valide → tâche créée, **rattachée au projet de l'URL**, redirection vers le détail du projet + message.
- Le formulaire de création **pré-sélectionne** `a_faire` / `moyenne` (GET → ces options sont `selected`).
- `title` vide → formulaire réaffiché avec erreur **visible dans le HTML**, aucune tâche créée.
- `status` / `priority` hors liste ou absent → erreur de formulaire (aucune tâche créée).
- **`due_date` au format `AAAA-MM-JJ` → acceptée et enregistrée** ; **édition d'une tâche datée → le HTML rend `value="AAAA-MM-JJ"`** (le widget ne se rouvre pas vide). Les deux tests du §6.
- `due_date` vide → tâche créée, `due_date` à `null`.
- `due_date` dans le passé → acceptée.
- **`project` injecté dans le POST → ignoré** : la tâche reste dans le projet de l'URL.
- Modification : changement de statut/priorité/échéance pris en compte ; le projet parent **ne change pas**.

**Suppression**
- POST → tâche supprimée, redirection vers le détail du projet + message.
- GET → page de confirmation, **ne supprime rien**.
- Le projet parent, lui, n'est pas supprimé.

**Non-régression**
- Les 135 tests existants passent toujours (dont ceux de la page de détail projet, enrichie ici).

## 9. Hors scope

- **Déplacer une tâche vers un autre projet** depuis le front : non exposé en V1. `project` n'est pas modifiable via le formulaire (l'API le permet, le front non — décision de simplicité, pas une contrainte technique). À rouvrir si le besoin apparaît.
- Page de détail de tâche isolée.
- Tri, pagination, filtres (tranche 5), tableau de bord (tranche 4).
- Actions groupées, sous-tâches, pièces jointes.
- V2 / collaboratif.
