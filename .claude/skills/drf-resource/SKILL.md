---
name: drf-resource
description: Procédure standard pour construire une ressource CRUD complète avec Django REST Framework dans TaskFlow (model → serializer → viewset → router → tests). À utiliser à chaque fois qu'on ajoute ou modifie une ressource exposée par l'API (Project, Task, etc.).
---

# drf-resource — Construire une ressource CRUD DRF (TaskFlow)

Procédure à suivre **dans l'ordre** pour créer une ressource CRUD complète. Elle
s'inscrit dans la méthode de travail du projet ([CLAUDE.md](../../../CLAUDE.md)) :
**SPEC.md validé → plan → code → tests qui passent → relecture par un subagent
reviewer**. Ce skill décrit la phase code+tests ; il ne dispense pas de la spec
ni du plan préalables.

Rappels de périmètre (V1) :
- Application **mono-utilisatrice** : chaque utilisateur ne voit et ne modifie
  que ses propres données. **Ne rien anticiper de la V2** (rôles, partage,
  owner/membre).
- Une app = une responsabilité : `projects` pour `Project`, `tasks` pour `Task`,
  code réellement partagé dans `core`.
- PEP 8, noms explicites, conventions Django/DRF idiomatiques.

Entités de référence utilisées comme exemples ci-dessous :

- **Project** : `name` (CharField, requis, max 200), `description` (TextField,
  optionnel), `owner` (FK → User, CASCADE), `created_at` (auto_now_add),
  `updated_at` (auto_now).
- **Task** : `title` (CharField, requis), `description` (TextField, optionnel),
  `status` (choices : à_faire / en_cours / terminé), `priority` (choices :
  basse / moyenne / haute), `due_date` (DateField, optionnel), `project`
  (FK → Project, CASCADE, `related_name='tasks'`), `created_at`, `updated_at`.

---

## 1. Le model (`models.py`)

- Déclarer les champs conformément au modèle de données validé. Ne pas ajouter
  de champ « au cas où » (pas de rôle, pas de flag collaboratif).
- Pour les champs à valeurs contraintes, définir les **choices via
  `TextChoices`** (ex. `Status`, `Priority`) plutôt que des tuples en dur : la
  source de vérité est unique et réutilisable.
- Définir une classe `Meta` :
  - `ordering` explicite (ex. `['-created_at']`) pour une pagination stable.
  - `verbose_name` / `verbose_name_plural` si le nom auto n'est pas satisfaisant.
- Définir `__str__` retournant une représentation lisible (`name` pour Project,
  `title` pour Task) — utile en admin et en debug.
- Générer et **relire** la migration (`makemigrations`) ; ne jamais éditer une
  migration déjà appliquée.

Exemple de structure attendue (pseudo-code, à ne pas implémenter ici) :

```
class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "a_faire", "À faire"
        IN_PROGRESS = "en_cours", "En cours"
        DONE = "termine", "Terminé"

    class Priority(models.TextChoices):
        LOW = "basse", "Basse"
        MEDIUM = "moyenne", "Moyenne"
        HIGH = "haute", "Haute"

    title = models.CharField(max_length=...)
    status = models.CharField(choices=Status.choices, default=Status.TODO, ...)
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                                related_name="tasks")
    ...

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
```

> Décision à trancher dans la spec : la valeur stockée pour les choices
> (`a_faire`/`termine` sans accents pour éviter les soucis d'encodage, ou libellé
> accentué). **Quelle que soit la décision, la même constante doit servir au
> model, au serializer et aux tests.**

## 2. Le serializer (`serializers.py`)

- Un `ModelSerializer` par ressource.
- **Exposer explicitement `fields`** (liste blanche) — ne jamais utiliser
  `fields = '__all__'`.
- Marquer en `read_only_fields` tout ce que le client ne doit pas fixer :
  `id`, `created_at`, `updated_at`, et surtout **`owner`** (rempli côté serveur,
  jamais depuis la requête — voir §3).
- **FK écrivable fournie par le client : restreindre le queryset du champ, pas
  écrire une `validate_<champ>()`.** Pour Task, `project` vient du client et ne
  doit désigner qu'un projet de l'utilisateur courant. La bonne approche est de
  restreindre le queryset du `PrimaryKeyRelatedField` :

  ```
  def get_fields(self):
      fields = super().get_fields()
      fields["project"].queryset = Project.objects.for_user(
          self.context["request"].user
      )
      return fields
  ```

  Noter le `for_user()` : le serializer réutilise le **manager de l'app**
  (cf. §3), il ne réécrit pas le filtre. C'est ce qui garantit que chemin de
  lecture et chemin d'écriture ne peuvent pas diverger.

  DRF rejette alors lui-même tout pk hors queryset (`does_not_exist` → 400),
  **en create comme en update**. Un objet d'autrui devient indiscernable d'un
  objet inexistant *par construction* — là où une `validate_<champ>()` manuelle
  doit reproduire ce camouflage à la main, et finit par diverger (cf. Pièges
  courants). Bonus : l'API browsable ne propose que les objets de l'utilisateur.
- Une `validate_<champ>()` reste légitime pour une **règle métier** (ex. cohérence
  entre deux champs), pas pour un contrôle d'appartenance exprimable par un
  queryset.
- Validations métier spécifiques au besoin (ex. `due_date` non antérieure à
  aujourd'hui) : uniquement si la spec le demande, pas par anticipation.
- Ne pas redéfinir à la main les choix de `status`/`priority` : laisser le
  serializer les dériver du champ model pour éviter la désynchronisation.

## 3. Le ViewSet (`views.py`)

- Un `ModelViewSet` par ressource, `permission_classes = [IsAuthenticated]`.
- **`get_queryset()` filtre TOUJOURS par utilisateur courant** — c'est la règle
  de sécurité centrale de la V1. **Ne pas réécrire l'expression du filtre à la
  main : elle vit dans un manager custom de l'app, `Model.objects.for_user()`**
  (cf. `core/SPEC-queries.md`), pour que ViewSets, serializers et vues front
  partagent la même source et ne divergent pas.
  - Project : `Project.objects.for_user(self.request.user)`
    (`ProjectQuerySet.for_user` → `filter(owner=user)`).
  - Task : `Task.objects.for_user(self.request.user)`
    (`TaskQuerySet.for_user` → `filter(project__owner=user).select_related("project")`).
  - **Nouvelle ressource** : lui donner son propre `XQuerySet.for_user(user)`
    dans son `models.py`, exposé par `objects = XQuerySet.as_manager()` — et
    l'utiliser partout, y compris dans les serializers (cf. §2).
- **`perform_create()` fixe l'owner côté serveur** :
  `serializer.save(owner=self.request.user)` pour Project. Ne jamais faire
  confiance à un `owner` envoyé par le client.
- Optimiser les accès liés avec `select_related` / `prefetch_related`
  (ex. `Task` → `select_related('project')`) pour éviter les N+1.
- Garder la logique métier hors des vues quand elle grossit ; les permissions
  réellement réutilisables vont dans `core`.

## 4. Le router (`urls.py`)

- Enregistrer le ViewSet dans un `DefaultRouter` :
  `router.register(r'projects', ProjectViewSet, basename='project')`.
- Fournir un **`basename` explicite** dès que `get_queryset` est surchargé
  (le router ne peut pas l'inférer sans `queryset` de classe).
- Câbler le router dans les `urls` de l'app, puis inclure l'app dans les `urls`
  racine sous un préfixe d'API cohérent (ex. `/api/`).
- Vérifier les noms d'URL générés (`project-list`, `project-detail`, …) : les
  tests s'appuient dessus via `reverse()`.

## 5. Les tests (`tests/`)

Chaque ressource s'accompagne de tests (exigence CLAUDE.md). Couvrir au minimum,
avec `APITestCase` et un utilisateur authentifié :

**Cas nominal (CRUD)**
- Création (`POST`) valide → 201, objet bien rattaché à l'utilisateur.
- Lecture liste (`GET`) → ne renvoie que les objets de l'utilisateur.
- Lecture détail (`GET /{id}`) → 200 pour un objet possédé.
- Mise à jour (`PUT`/`PATCH`) → 200 et modification effective.
- Suppression (`DELETE`) → 204 et objet réellement supprimé.

**Cas limites / validation**
- Champ requis manquant (`name` / `title` vide) → 400.
- Valeur de choice invalide (`status`/`priority` hors liste) → 400.
- Task : `project` inexistant ou appartenant à un autre utilisateur → 400/404
  (ne doit pas permettre de rattacher une tâche au projet d'autrui).
- `due_date` mal formée / règle métier si spec.

**Permissions / isolation par utilisateur**
- Un utilisateur B **ne voit pas** les objets de A (liste filtrée).
- B reçoit **404** (pas 403) en détail/update/delete sur un objet de A —
  l'objet ne doit pas être distinguable de « inexistant ».
- Requête **non authentifiée** → 401/403.

Viser des tests lisibles et indépendants (chaque test crée ses propres données).

---

## Pièges courants (gotchas)

### Principe général — valider contre le bon périmètre, avec les bonnes valeurs

**Le même bug est revenu trois fois sous trois déguisements** (les trois incidents
du 2026-07-14 ci-dessous). À chaque fois, une brique de vérification — contrôle
d'appartenance d'une FK, validation d'unicité, filtre sur une relation — a
interrogé un ensemble **plus large**, ou des **valeurs différentes**, que ce que
l'utilisateur peut légitimement voir et que la base applique réellement. La
vérification diverge alors de la réalité, et **la divergence devient
observable** : soit un *oracle* (200 vs 400, ou deux corps d'erreur différents)
qui révèle l'existence de données d'autrui, soit un **500** sur un conflit que la
validation a manqué.

**Réflexe à avoir AVANT d'écrire une FK écrivable, un filtre, ou une validation
d'unicité :** contre quel ensemble cette brique valide-t-elle, et est-ce
*exactement* le périmètre visible par l'utilisateur (`Model.objects.filter(
owner=user)`, jamais `Model.objects.all()`) et *exactement* la valeur qui sera
écrite en base ? Si elle regarde plus large, ou une autre valeur, elle fuira ou
plantera. Se tester par **égalité stricte des corps de réponse** (pas le seul
code HTTP) pour les cas censés être indiscernables.

Les trois incidents, même famille :

- **FK écrivable validée contre tous les objets — `project` de Task.** Le
  `PrimaryKeyRelatedField` acceptait n'importe quel projet existant ; une
  `validate_project()` maison tentait de rejeter ceux d'autrui. Deux fuites :
  - son **queryset** portait sur `Project.objects.all()`, donc un projet
    d'autrui était distinguable d'un pk inexistant. **Fix : restreindre le
    queryset du champ** à `Project.objects.for_user(request.user)` (cf. §2)
    → objet d'autrui indiscernable de l'inexistant, par construction.
  - elle **recopiait à la main** le message d'erreur de DRF pour « camoufler »
    le cas. Mais `LANGUAGE_CODE='en-us'` : DRF répond `Invalid pk "3" - object
    does not exist.` en anglais, quand le code renvoyait la version française.
    Mêmes 400, **corps différents** → oracle. **Règle : ne jamais dupliquer à la
    main une chaîne d'erreur interne d'une lib** (traduite, versionnée, elle
    diverge) ; déléguer au mécanisme natif (queryset restreint ; à défaut
    `self.fields[x].fail("does_not_exist", ...)`).
- **Validation d'unicité sur une valeur ≠ valeur écrite — inscription.**
  `create_user()` normalise avant l'`INSERT` (`normalize_email` : domaine en
  minuscules ; `normalize_username` : NFKC), mais l'`UniqueValidator` et la
  relecture de rattrapage interrogeaient la base avec la valeur **brute**.
  `aude@EXAMPLE.COM`, ou un username `ａｕｄｅ` (pleine chasse), passaient la
  validation puis heurtaient la contrainte à l'écriture → **500 déclenchable
  sans concurrence**. **Fix : valider / relire avec la valeur normalisée**
  (`normalize_email`, `normalize_username`), celle réellement écrite. La brique
  doit regarder ce que la base applique, pas ce que le client a tapé.
- **Filtre de relation validé contre tous les objets — `ModelChoiceFilter`
  auto.** Lister une FK dans `Meta.fields` d'une `FilterSet` django-filter
  génère un `ModelChoiceFilter` dont le queryset de validation est
  `Model.objects.all()` (tous les utilisateurs) : `project=<pk inexistant>`
  renvoyait 400 alors que `project=<projet d'autrui>` renvoyait 200 `[]` →
  oracle d'existence. **Fix : déclarer un `NumberFilter(field_name="project")`
  explicite** — tout pk hors du queryset (déjà filtré par utilisateur) donne
  simplement `[]`, sans validation contre la base globale.

### Autres pièges

- **Oublier de filtrer le queryset par utilisateur.** Un `queryset` de classe
  non surchargé expose les données de tout le monde. Toujours passer par
  `get_queryset()` filtré, et le tester explicitement (utilisateur B).
- **Faire confiance à `owner` venant du client.** L'owner doit être fixé dans
  `perform_create` et être `read_only` dans le serializer, sinon un client peut
  créer/voler des objets au nom d'un autre.
- **Choices désynchronisés entre model et serializer/tests.** Utiliser une
  source unique (`TextChoices`) et réutiliser ces constantes partout ; ne pas
  recopier `"en_cours"` en dur dans les tests.
- **Accents/encodage dans les valeurs stockées.** Décider une bonne fois si la
  valeur en base est accentuée ou non, et s'y tenir (le libellé accentué reste
  dans le second élément du choice).
- **N+1 queries.** Sérialiser une liste de Task qui accède à `project` sans
  `select_related('project')` déclenche une requête par tâche. Ajouter
  `select_related`/`prefetch_related` dans `get_queryset`.
- **`fields = '__all__'`.** Expose des champs sensibles/internes et casse
  silencieusement le contrat d'API quand le model évolue. Lister les champs.
- **`basename` manquant au router** quand `queryset` de classe est absent →
  erreur au chargement des URLs.
- **404 vs 403 pour l'isolation.** Renvoyer 403 sur l'objet d'un autre
  utilisateur révèle son existence. Le filtrage par `get_queryset` donne
  naturellement un 404, ce qui est le comportement attendu.
- **Retour à 403 sur suppression en cascade oublié.** `on_delete=CASCADE` sur
  `project` supprime les tâches liées : le vérifier dans un test plutôt que de
  le découvrir en prod.
- **Anticiper la V2.** Pas de champ `role`, `members`, ni permission
  collaborative « au cas où ». On reste sur le modèle solo.
