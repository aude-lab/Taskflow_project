# SPEC — Front, tranche 1 : socle et authentification

## 1. Objectif

Poser le socle du front (layout Bootstrap, navigation, messages) et l'authentification par **session Django** : inscription, connexion, déconnexion, page d'accueil protégée. Les tranches suivantes (projets, tâches, dashboard) s'appuieront dessus.

## 2. Périmètre de cette tranche

**Inclus** : `base.html`, navigation, pages login / logout / inscription, page d'accueil protégée (placeholder du futur dashboard), règles d'accès.

**Exclu, chacun sa tranche** : CRUD projets, CRUD tâches, tableau de bord, filtres, gestion du compte (édition profil, changement de mot de passe), réinitialisation de mot de passe.

## 3. Architecture

| Élément | Emplacement |
|---------|-------------|
| Layout partagé | `core/templates/base.html` |
| Page d'accueil | `core/views_web.py` → `HomeView` ; `core/templates/core/home.html` |
| Pages d'auth | `accounts/views_web.py` ; `accounts/templates/accounts/*.html` |
| Formulaire d'inscription | `accounts/forms.py` → `RegistrationForm` |
| URLs front | `core/urls_web.py` et `accounts/urls_web.py`, inclus **à la racine** (sans préfixe `/api/`) |

`APP_DIRS = True` est déjà actif : les dossiers `templates/` des apps sont trouvés sans configuration supplémentaire.

**Le front (session) et l'API (JWT) sont indépendants.** On n'ajoute **pas** `SessionAuthentication` à `DEFAULT_AUTHENTICATION_CLASSES` : l'API reste en JWT seul. Se connecter au front ne donne aucun accès à l'API, et réciproquement — deux mécanismes distincts, sans couplage ni surface CSRF supplémentaire côté API.

## 4. Pages et URLs

| URL | Vue | Accès | Rôle |
|-----|-----|-------|------|
| `/` | `HomeView` | connecté | Accueil ; placeholder du futur dashboard |
| `/inscription/` | `RegistrationView` | anonyme | Créer un compte, puis connexion automatique |
| `/connexion/` | `LoginView` (Django) | anonyme | Se connecter |
| `/deconnexion/` | `LogoutView` (Django) | connecté | Se déconnecter (**POST uniquement**, cf. §6) |

Réglages `settings.py` : `LOGIN_URL = "/connexion/"`, `LOGIN_REDIRECT_URL = "/"`, `LOGOUT_REDIRECT_URL = "/connexion/"`.

## 5. Layout (`base.html`)

- Bootstrap servi par **CDN** (`<link>` CSS, `<script>` JS en fin de body).
- Blocs `{% block title %}` et `{% block content %}`.
- **Barre de navigation conditionnelle** : si connecté → nom d'utilisateur + bouton de déconnexion ; sinon → liens Connexion / Inscription. Les liens vers projets, tâches et dashboard seront ajoutés par les tranches suivantes.
- **Affichage des messages** (`django.contrib.messages`, déjà installé) en alertes Bootstrap.
- Toutes les pages en étendent (`{% extends "base.html" %}`).

## 6. Règles d'accès et points de vigilance

- **`LoginRequiredMixin` est obligatoire sur toute vue front manipulant des données utilisateur.** Ce n'est pas cosmétique : les managers `for_user()` supposent un utilisateur authentifié (cf. `projects/SPEC.md` §7). Une vue non protégée recevrait un `AnonymousUser` et lèverait une **erreur 500** au lieu de rediriger vers la connexion. On s'appuie sur le `LoginRequiredMixin` de Django, sans wrapper maison.
- **La déconnexion doit se faire en POST.** Depuis Django 5, `LogoutView` refuse `GET` : la navigation utilise un petit `<form method="post">` avec `{% csrf_token %}`, pas un simple lien. Un `<a href="/deconnexion/">` donnerait un **405**.
- **`{% csrf_token %}` dans tous les formulaires** (connexion, inscription, déconnexion).
- Un utilisateur **déjà connecté** qui visite `/connexion/` ou `/inscription/` est redirigé vers `/` (pas de formulaire de connexion affiché à quelqu'un de connecté).

## 7. Inscription (`RegistrationForm`)

`ModelForm` dérivé de `UserCreationForm` (Django), sur le modèle `accounts.User` :

- Champs : `username`, `email`, `password1`, `password2`.
- `UserCreationForm` fournit déjà la **confirmation du mot de passe** et applique `AUTH_PASSWORD_VALIDATORS` — rien à réécrire.
- `email` est rendu **obligatoire** (le modèle le contraint déjà en `unique`, cf. `accounts/SPEC.md`) ; l'unicité remonte donc en erreur de formulaire, pas en 500.
- Le mot de passe est hashé par `UserCreationForm.save()` (`set_password`) — **jamais** de création d'utilisateur en clair.
- Après inscription réussie : **connexion automatique** (`login()`) puis redirection vers `/`.

> Cette tranche ne touche **pas** `RegisterSerializer` ni `/api/register/` : le front a son propre chemin, l'API garde le sien. Les deux s'appuient sur le même modèle et les mêmes validateurs de mot de passe.

## 8. Cas limites à couvrir (tests)

**Accès**
- Anonyme sur `/` → **302** vers `/connexion/` (et surtout **pas** de 500).
- Connecté sur `/` → **200**, la page affiche son nom d'utilisateur.
- Connecté sur `/connexion/` ou `/inscription/` → **302** vers `/`.

**Connexion / déconnexion**
- Identifiants valides → **302** vers `/`, session ouverte.
- Identifiants invalides → **200** (formulaire réaffiché avec erreur), session **non** ouverte.
- Déconnexion en **POST** → **302**, session fermée.
- Déconnexion en **GET** → **405** (comportement attendu de Django, à documenter par un test).

**Inscription**
- Données valides → utilisateur créé, **connecté automatiquement**, redirection vers `/`.
- **Mot de passe hashé en base** : `user.password != "<clair>"` et `check_password("<clair>")` vrai (même garde-fou que côté API).
- `username` déjà pris → formulaire réaffiché avec erreur, **aucun utilisateur créé**.
- `email` déjà pris → idem (erreur de formulaire, pas une 500).
- Mots de passe différents → erreur, aucun utilisateur créé.
- Mot de passe trop faible → erreur, aucun utilisateur créé.

**Non-régression**
- Les 97 tests existants (API) continuent de passer : cette tranche n'ajoute que des vues, aucun changement de modèle ni de comportement API.

## 9. Hors scope

- Édition du profil, changement et réinitialisation de mot de passe.
- « Se souvenir de moi », expiration de session personnalisée.
- Toute page projets / tâches / dashboard (tranches suivantes).
- Design au-delà de Bootstrap par défaut ; pas de CSS custom au-delà du strict nécessaire.
- V2 / collaboratif.
