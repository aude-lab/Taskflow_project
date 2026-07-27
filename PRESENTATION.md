# TaskFlow — présentation technique et journal d'apprentissage

> Ce document complète le [README](README.md). Le README dit *ce que fait* le projet ;
> celui-ci raconte *comment il est construit*, *pourquoi* j'ai fait tels choix, et
> surtout **les problèmes que j'ai rencontrés et ce qu'ils m'ont appris**. Je l'ai
> écrit autant pour un visiteur curieux que pour moi-même, pour fixer mes acquis.

---

## 1. En deux mots

TaskFlow est une petite application de **gestion de projets et de tâches**, que
j'ai réalisée en solo pendant mes vacances de ING1 à EPITA PARIS. Une utilisatrice
crée des projets, y ajoute des tâches (avec un statut, une priorité, une échéance),
et retrouve tout sur un tableau de bord avec des filtres. Une version minimal de Gitlab.

**Le but premier n'était pas de livrer vite, mais d'apprendre en profondeur** :
comprendre Django et Django REST Framework, et surtout me forcer à une méthode
de travail rigoureuse. J'ai codé avec l'aide d'un agent IA (Claude Code), mais
la conception, les choix d'architecture et la validation de chaque étape sont les
miens — l'IA a été un binôme exigeant, pas un pilote automatique.

Le projet expose **deux visages** de la même application :

- une **API REST** (authentifiée par jetons JWT), pensée pour être consommée par
  n'importe quel client ;
- un **site web classique** (formulaires Django, sessions), avec pages HTML et
  Bootstrap.

Les deux partagent exactement le même cœur métier. C'est un fil rouge de tout le
projet : **une règle métier ne doit exister qu'à un seul endroit.**

---

## 2. Ce que l'application sait faire (V1)

| Domaine | Côté API (JWT) | Côté site web (session) |
|---|---|---|
| **Comptes** | inscription, obtention/rafraîchissement de jeton | inscription, connexion, déconnexion |
| **Projets** | créer, lister, voir, modifier, supprimer | idem, avec pages et formulaires |
| **Tâches** | idem + filtres (projet, statut, priorité, échéance) | idem + liste filtrable |
| **Tableau de bord** | endpoint `/api/dashboard/` | page d'accueil |
| **Administration** | admin Django natif | — |

Chaque utilisatrice ne voit **que ses propres données** : c'est une application
mono-utilisatrice (la version collaborative « V2 » n'existe pas encore, et je me
suis interdit de l'anticiper dans le code).

---

## 3. La pile technique

| Outil | Rôle | Version |
|---|---|---|
| **Python / Django** | le framework web | Django 6.0 |
| **Django REST Framework** | l'API REST | 3.17 |
| **djangorestframework-simplejwt** | l'authentification par jetons JWT | 5.5 |
| **django-filter** | les filtres de l'API (et réutilisés par le site) | 26.1 |
| **PostgreSQL** (via `psycopg`) | la base de données | psycopg 3.3 |
| **python-dotenv** | charger les secrets depuis un fichier `.env` | 1.2 |
| **Bootstrap 5** | le style du site web (servi par CDN) | 5.3 |

---

## 4. Comment c'est organisé

Le projet suit le principe **« une app = une responsabilité »** :

```
taskflow/        → configuration du projet (settings, urls racine)
accounts/        → l'utilisatrice et l'authentification
projects/        → les projets (modèle Project + son CRUD)
tasks/           → les tâches (modèle Task, filtres, tableau de bord)
core/            → le socle partagé (page d'accueil, base HTML, mixin de formulaire)
```

Dans chaque app, on retrouve deux « familles » de fichiers, une par visage de
l'application :

- `views.py`, `serializers.py`, `urls.py` → l'**API** (DRF) ;
- `views_web.py`, `forms.py`, `urls_web.py`, `templates/` → le **site web** (Django classique).

### La pièce d'architecture dont je suis la plus fière : « qui voit quoi » à un seul endroit

Le risque numéro un d'une appli multi-utilisateurs, c'est qu'un utilisateur voie
les données d'un autre. La règle « ne montrer que les données de l'utilisateur »
apparaît à *beaucoup* d'endroits : dans l'API, dans les formulaires, dans le site,
dans le tableau de bord. Si je la réécris à la main partout, le jour où je la
change à un endroit et pas à un autre → faille.

J'ai donc mis cette règle dans un **manager personnalisé**, une seule fois par
modèle :

```python
# projects/models.py
class ProjectQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(owner=user)

class Project(models.Model):
    ...
    objects = ProjectQuerySet.as_manager()
```

Du coup, **partout** — API, formulaires, site, dashboard — j'écris simplement
`Project.objects.for_user(user)` ou `Task.objects.for_user(user)`. La règle vit
à un seul endroit ; elle ne peut pas diverger.

> Petite histoire dans l'histoire : au départ j'avais mis ces requêtes dans un
> fichier `core/queries.py`. Mais ça faisait dépendre `core` (censé être la brique
> « feuille », dont tout le monde dépend) des apps métier `projects` et `tasks` —
> une inversion de dépendance fragile. Je suis passée aux managers, qui remettent
> la règle **dans l'app qui possède le modèle**. `core/queries.py` a été supprimé.
> Ça m'a appris à faire attention au **sens des dépendances** entre modules.

Même idée pour le tableau de bord : la définition de « en retard / à venir / par
statut » vit dans **une seule fonction** `tasks/dashboard.py::build_dashboard(user)`,
appelée à la fois par l'API et par la page d'accueil. Les deux ne peuvent pas se
contredire.

---

## 5. Ma méthode de travail (le vrai sujet du projet)

Pour chaque fonctionnalité, je me suis imposé le même rituel, sans sauter d'étape :

1. **Spec avant code.** J'écris un petit `SPEC.md` : l'objectif, le périmètre, les
   champs/endpoints concernés, et surtout **les cas limites**. Le dépôt contient
   une douzaine de ces specs (une par ressource / fonctionnalité).
2. **Plan avant d'éditer.** Je liste les fichiers touchés et les étapes, et je
   valide avant de toucher au code.
3. **Pas de « c'est fini » sans preuve.** Une fonctionnalité n'est terminée que
   quand ses tests passent, sortie à l'appui.
4. **Relecture avant de clôturer.** Je fais relire le diff (par un agent relecteur)
   avant de considérer une étape close. Plusieurs vrais bugs ont été attrapés là.
5. **Incrémental.** Le front a été construit en tranches (auth → projets → tâches →
   dashboard → filtres → polish), chacune validée avant la suivante.

Côté Git, je travaille sur une branche `test`, et je ne fusionne dans `main`
qu'une fois tout vert et relu.

**Ce que j'en retiens** : la spec et les tests ne « ralentissent » pas, ils
évitent de coder le mauvais truc et de le découvrir trop tard. La plupart des
bugs ci-dessous ont été trouvés *parce que* j'avais des cas limites écrits noir
sur blanc.

À la fin de la V1 : **188 tests automatisés**, tous verts.

---

## 6. Les problèmes rencontrés, et ce qu'ils m'ont appris

C'est la section la plus importante pour moi. Chaque bug m'a appris quelque chose
de concret. Je les garde ici pour ne pas les refaire.

### 6.1. LA grande leçon : « valider contre le bon périmètre »

Le même bug est revenu **trois fois** sous des déguisements différents. À chaque
fois, une petite brique (une validation, un filtre) vérifiait quelque chose contre
un ensemble **plus large** que ce que l'utilisateur a le droit de voir — et ça
créait une fuite d'information.

**Déguisement n°1 — un message d'erreur qui trahit.**
Quand on crée une tâche, on choisit son projet parent. Je vérifiais « ce projet
t'appartient-il ? » et, sinon, je renvoyais un message d'erreur *écrit à la main
en français* pour faire croire que le projet « n'existe pas ». Sauf que Django
répondait, lui, en anglais (la langue était réglée sur `en-us` à ce moment-là).
Résultat : « projet qui n'existe pas » et « projet de quelqu'un d'autre »
renvoyaient deux messages **différents** → un attaquant pouvait deviner quels
projets existent.
**Correctif :** ne jamais recopier à la main un message d'une bibliothèque.
J'ai plutôt **restreint le champ** pour qu'il n'accepte que mes propres projets ;
Django rejette alors tout le reste de façon identique.

**Déguisement n°2 — un filtre trop généreux.**
Pour filtrer les tâches par projet dans l'API, j'avais laissé django-filter
générer automatiquement le filtre. Il validait le projet contre **tous** les
projets de la base. Du coup : un projet inexistant → erreur 400, mais un projet
appartenant à quelqu'un d'autre → 200 avec liste vide. Encore une fois, la
différence de réponse trahissait l'existence des projets des autres.
**Correctif :** un simple filtre numérique appliqué sur mes propres tâches — un
identifiant hors de mon périmètre ne correspond alors à rien, sans distinction.

**Déguisement n°3 (variante) — valider une valeur, en écrire une autre.**
À l'inscription, Django « normalise » l'email (il met le domaine en minuscules)
et le nom d'utilisateur (normalisation Unicode) **avant** de l'enregistrer. Mais
je vérifiais l'unicité sur la valeur **brute** tapée par l'utilisateur. Donc
`aude@EXAMPLE.COM` passait la vérification (rien trouvé), puis se cognait à la
base à l'écriture → **erreur 500**, sans même qu'il y ait deux personnes en même
temps. **Correctif :** vérifier l'unicité sur la valeur *réellement écrite*
(normalisée), pas sur celle reçue.

**La règle générale que j'en tire :** avant d'écrire une validation, un filtre ou
une vérification d'unicité, je me demande toujours : *« Contre quel ensemble je
vérifie, et est-ce exactement ce que l'utilisateur a le droit de voir, et
exactement la valeur qui sera enregistrée ? »*

### 6.2. Deux inscriptions au même instant (fenêtre de course)

Même si l'email est unique en base, deux inscriptions simultanées avec le même
email pouvaient toutes deux passer la validation (qui interroge la base), puis la
seconde échouait à l'écriture avec une erreur brute → **500**, alors qu'une
inscription en double devrait juste afficher un message poli.
**Correctif :** entourer l'écriture d'un `try/except` qui attrape l'erreur de la
base et la transforme en une erreur de formulaire propre (400), comme n'importe
quelle autre. **Leçon :** la validation applicative ne remplace pas la contrainte
de la base ; il faut gérer le cas où c'est la base qui a le dernier mot.

### 6.3. Le calendrier qui s'ouvre vide (le piège de la date en français)

Le champ de date HTML (`<input type="date">`) envoie toujours la date au format
`AAAA-MM-JJ`. Mais comme j'avais réglé la langue sur le français, Django la
ré-affichait au format `JJ/MM/AAAA` — que le calendrier HTML **ne comprend pas**.
Résultat : quand on rouvrait une tâche déjà datée pour la modifier, le champ de
date apparaissait **vide**, et on risquait d'effacer l'échéance sans le vouloir.
**Correctif :** forcer le champ à ré-afficher la date au format `AAAA-MM-JJ`.
**Leçon :** changer la langue d'un projet a des effets de bord inattendus (les
formats de date !), et « ça marche à la création » ne veut pas dire « ça marche à
la modification » — il faut tester le ré-affichage, pas seulement la saisie.

### 6.4. Le bouton « Déconnexion » qui renvoyait une erreur

Depuis Django 5, on ne peut plus se déconnecter avec un simple lien : il faut un
vrai formulaire (méthode POST). Un lien classique renvoie une erreur 405.
**Correctif :** un petit `<form>` avec un bouton stylé en lien. **Leçon :** lire
les notes de version de son framework ; des comportements « évidents » changent.

### 6.5. Un commentaire qui s'affiche à l'écran

Sur le tableau de bord, un bloc de texte gris bizarre apparaissait dans mes
encadrés. C'était… un **commentaire** de template censé être invisible. En Django,
la syntaxe de commentaire courte `{# ... #}` ne fonctionne **que sur une seule
ligne** ; le mien tenait sur deux lignes, donc Django l'affichait tel quel.
**Correctif :** utiliser `{% comment %}...{% endcomment %}` pour le multi-ligne.
**Leçon (la plus humble)** : mes tests vérifiaient que les *bons* textes étaient
présents, mais pas l'*absence* de parasites. J'ai ajouté un test qui vérifie que
le commentaire n'apparaît **pas**. Ce bug-là, c'est en regardant la vraie page
que je l'ai vu — les tests seuls ne suffisent pas, il faut aussi *regarder*.

### 6.6. Deux menus allumés en même temps

Dans la barre de navigation, je surlignais l'onglet courant en regardant l'URL.
Mais l'adresse pour créer une tâche est `/projets/<id>/taches/nouvelle/` — elle
contient à la fois « projets » **et** « taches » → les deux onglets s'allumaient.
**Correctif :** me baser sur le *nom* de l'URL (`project_...` ou `task_...`),
pas sur le texte de l'adresse. **Leçon :** se repérer sur une donnée structurée
(le nom de route) plutôt que sur une chaîne de caractères ambiguë.

### 6.7. Les tests qui n'osaient pas planter la base

Petit obstacle d'installation : le test-runner de Django crée une base jetable
`test_taskflow`, ce qui demande au compte PostgreSQL le droit de **créer des
bases** (`CREATEDB`). Sans ce droit, aucun test ne tourne. Une ligne SQL à lancer
une fois (`ALTER ROLE ... CREATEDB;`) et c'était réglé. **Leçon :** l'environnement
de test fait partie du projet, pas juste le code.

### 6.8. Une bonne surprise : la valeur par défaut n'est pas magique

Je pensais que si l'utilisateur ne choisissait pas de statut, la valeur par défaut
du modèle s'appliquerait toute seule. En réalité, un formulaire Django rend ces
champs **obligatoires** (il pré-sélectionne juste le défaut dans le menu déroulant).
Ça m'a obligée à clarifier ce que « valeur par défaut » veut vraiment dire selon
qu'on parle du modèle ou du formulaire.

---

## 7. Une philosophie des tests : « un test doit pouvoir échouer »

Un test qui passe toujours, quoi qu'il arrive, ne protège de rien. À chaque fois
que je corrigeais un bug important, je **vérifiais que le test correspondant
échouait bien sur l'ancien code buggé** avant de valider le correctif — sinon,
comment être sûre qu'il teste vraiment quelque chose ?

Concrètement, je remettais temporairement le bug (par exemple : « et si je ne
restreins plus la liste aux tâches de l'utilisateur ? ») et je vérifiais que le
test d'isolation **tombait en rouge**. Puis je remettais le bon code. Ça donne une
vraie confiance dans le filet de sécurité.

---

## 8. Lancer le projet chez soi

Prérequis : Python 3.12+, PostgreSQL.

```bash
# 1. Récupérer le code et créer un environnement virtuel
git clone https://github.com/aude-lab/Taskflow_project.git
cd Taskflow_project
python -m venv venv
source venv/bin/activate            # sous Windows : venv\Scripts\activate
pip install -r requirements.txt

# 2. Configurer les secrets : copier l'exemple et remplir les valeurs
cp .env.example .env
#   → éditer .env : SECRET_KEY, identifiants PostgreSQL (DB_NAME, DB_USER, DB_PASSWORD…)

# 3. Créer la base PostgreSQL correspondante, puis :
python manage.py migrate
python manage.py createsuperuser

# 4. Lancer le serveur
python manage.py runserver
#   → site web : http://localhost:8000/
#   → admin    : http://localhost:8000/admin/
```

Le fichier `.env` **n'est jamais versionné** (il contient des secrets) ; seul
`.env.example`, sans valeurs sensibles, est dans le dépôt.

### Lancer les tests

```bash
python manage.py test
```

> Si les tests refusent de démarrer avec une erreur de permission, il faut donner
> au compte PostgreSQL le droit de créer des bases (voir § 6.7) :
> `sudo -u postgres psql -c "ALTER ROLE taskflow CREATEDB;"`

---

## 9. Aperçu des points d'entrée de l'API

Tout est préfixé par `/api/`. L'authentification se fait par jeton JWT
(`POST /api/token/` avec identifiants → jeton à mettre dans l'en-tête
`Authorization: Bearer ...`).

| Méthode | URL | Rôle |
|---|---|---|
| `POST` | `/api/register/` | créer un compte |
| `POST` | `/api/token/` | obtenir un jeton |
| `GET/POST` | `/api/projects/` | lister / créer des projets |
| `GET/POST` | `/api/tasks/` | lister (filtrable) / créer des tâches |
| `GET` | `/api/dashboard/` | tableau de bord (en retard / à venir / par statut) |

Exemple de filtre : `GET /api/tasks/?status=en_cours&priority=haute&due_date_before=2026-12-31`.

---

## 10. Ce qui n'est volontairement PAS fait

Je préfère être honnête sur les limites que faire semblant :

- **Pas de collaboration (V2).** L'appli est mono-utilisatrice. Je me suis
  interdit d'ajouter le moindre champ « au cas où » pour le collaboratif — coder
  pour un besoin qui n'existe pas encore, c'est de la complexité gratuite.
- **Pas de pagination** sur les listes : la V1 suppose un volume raisonnable de
  tâches par personne.
- **Deux limites mineures assumées** : l'unicité de l'email ne distingue pas la
  casse de la partie locale (`Aude@…` et `aude@…` sont considérés différents), et
  côté site web une valeur de filtre invalide dans une URL forgée est simplement
  ignorée (page normale) au lieu de renvoyer une erreur — un site web n'a pas à se
  comporter comme une API stricte.
- **Pas de déploiement en production** : le projet tourne en local (serveur de
  développement), l'objectif étant l'apprentissage.

---

## 11. Note sur la collaboration avec l'IA

J'ai écrit ce projet avec Claude Code comme binôme. Mais je tiens à être claire :
**les décisions sont les miennes.** À chaque étape, j'ai validé la spec, choisi
l'architecture, tranché les points ouverts (quelles couleurs pour les badges, faut-il
un manager ou un module partagé, etc.). L'IA a proposé, expliqué, écrit du code et
relu — et plusieurs fois, une relecture par un second agent a attrapé un vrai bug
avant que je ne clôture une étape. C'est exactement le genre de garde-fou que je
voulais apprendre à mettre en place.

Ce que je retiens du projet, au-delà de Django : **une méthode**. Écrire ce qu'on
va faire avant de le faire, se donner des cas limites, prouver que ça marche,
faire relire, avancer par petits pas. C'est ça, pour moi, le vrai livrable.
