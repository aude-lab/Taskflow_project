# SPEC — Front, tranche 2 : CRUD projets

## 1. Objectif

Permettre à l'utilisateur connecté de gérer ses projets depuis l'interface web : lister, consulter, créer, modifier, supprimer.

## 2. Périmètre

**Inclus** : les cinq pages de gestion des projets, leur navigation, et l'ajout d'un lien « Projets » dans `base.html`.

**Exclu, tranches suivantes** : les tâches (la page de détail d'un projet réservera l'emplacement de sa liste de tâches, sans l'implémenter), le tableau de bord, les filtres.

## 3. Architecture

| Élément | Emplacement |
|---------|-------------|
| Vues | `projects/views_web.py` |
| Formulaire | `projects/forms.py` → `ProjectForm` |
| URLs | `projects/urls_web.py`, inclus à la racine |
| Templates | `projects/templates/projects/` |

Vues génériques Django (`ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView`), toutes avec `LoginRequiredMixin`.

## 4. Pages et URLs

| URL | Vue | Rôle |
|-----|-----|------|
| `/projets/` | `ProjectListView` | Liste des projets de l'utilisateur |
| `/projets/nouveau/` | `ProjectCreateView` | Créer un projet |
| `/projets/<pk>/` | `ProjectDetailView` | Détail (emplacement réservé pour les tâches) |
| `/projets/<pk>/modifier/` | `ProjectUpdateView` | Modifier |
| `/projets/<pk>/supprimer/` | `ProjectDeleteView` | Confirmer puis supprimer (**suppression en POST**) |

Après création, modification ou suppression : redirection vers `/projets/` avec un message de succès.

## 5. Sécurité

Applique le **principe général** du skill `drf-resource`, exactement comme l'API :

- **`LoginRequiredMixin` sur les cinq vues.** Sans lui, `for_user()` recevrait un `AnonymousUser` → 500 au lieu d'une redirection.
- **`get_queryset()` renvoie toujours `Project.objects.for_user(self.request.user)`** (cf. `projects/SPEC.md` §7), jamais `Project.objects.all()`. Conséquence : un projet d'un autre utilisateur donne **404** en détail / modification / suppression — cohérent avec l'API, et son existence n'est pas révélée.
- **`owner` n'est jamais un champ du formulaire.** Il est fixé côté serveur dans `form_valid()` (`form.instance.owner = self.request.user`), comme `perform_create` côté API. Un `owner` injecté dans le POST est donc ignoré.
- `{% csrf_token %}` sur tous les formulaires, y compris celui de suppression.

## 6. Formulaire (`ProjectForm`)

`ModelForm` sur `Project`, champs **`name` et `description` uniquement**, stylé par `BootstrapFormMixin`.

> **Point de vigilance — l'unicité `(owner, name)` n'est pas validée automatiquement.**
> Le modèle porte `unique_together = [["owner", "name"]]`, mais `owner` n'étant pas un champ du formulaire, Django l'exclut de `validate_unique()` : la contrainte composite est alors **ignorée à la validation**, et le doublon n'échoue qu'à l'`INSERT` → **`IntegrityError`, donc 500**.
>
> C'est exactement le piège déjà rencontré côté API (`ProjectSerializer.validate_name`) et documenté dans le skill : une brique qui valide contre un périmètre différent de celui que la base applique.
>
> **Solution** : le formulaire reçoit l'utilisateur (via `get_form_kwargs()`) et vérifie l'unicité dans `clean_name()` :
> `Project.objects.for_user(user).filter(name=value)`, en **excluant l'instance courante** en modification (sinon renommer un projet en conservant son nom échouerait). Mêmes règles et même manager que l'API.

## 7. Pages, contenu attendu

- **Liste** : nom, date de création, **nombre de tâches**, et liens vers détail / modification / suppression. Bouton « Nouveau projet ». État vide explicite si aucun projet.
  - Le nombre de tâches est obtenu par **agrégation** (`annotate(Count("tasks"))`), pas par une requête par ligne : la liste doit rester à un nombre de requêtes constant, quel que soit le nombre de projets.
- **Détail** : nom, description, dates ; emplacement réservé pour la future liste des tâches ; liens modifier / supprimer.
- **Création / modification** : le même template de formulaire, titre adapté.
- **Suppression** : page de confirmation qui **indique combien de tâches seront supprimées avec le projet** (`on_delete=CASCADE`), pour que la conséquence soit visible avant de valider.

## 8. Cas limites à couvrir (tests)

**Isolation**
- Liste : ne contient que les projets de l'utilisateur.
- Détail / modification / suppression d'un projet d'un autre utilisateur → **404**.
- Anonyme sur chacune des cinq URLs → **302** vers la connexion (jamais 500).

**Création / modification**
- Création valide → projet créé, **`owner` = utilisateur courant**, redirection + message.
- `owner` injecté dans le POST → **ignoré**, l'owner reste l'utilisateur courant.
- `name` vide → formulaire réaffiché avec erreur **visible dans le HTML**, aucun projet créé.
- `name` > 200 caractères → erreur.
- **`name` déjà utilisé par un autre projet du même utilisateur → erreur de formulaire (200), et surtout pas une 500.**
- Le même `name` chez un **autre** utilisateur → **autorisé**.
- Modification conservant son propre nom → acceptée.
- Modification vers le nom d'un **autre** de ses projets → erreur.

**Suppression**
- POST sur la confirmation → projet supprimé, redirection + message.
- **Les tâches du projet sont supprimées en cascade**, celles des autres projets non.
- GET sur l'URL de suppression → affiche la page de confirmation, **ne supprime rien**.

**Performance**
- La liste exécute un **nombre de requêtes constant**, indépendant du nombre de projets (test par `assertNumQueries`).

## 9. Hors scope

- Tâches (création, liste, rattachement) : tranche suivante.
- Pagination de la liste, tri, recherche.
- Suppression en masse, archivage.
- V2 / collaboratif.
