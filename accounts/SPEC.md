# SPEC — Inscription (accounts)

## 1. Objectif

Permettre à une visiteuse de créer son compte et d'obtenir immédiatement ses tokens JWT, sans étape de connexion supplémentaire.

## 2. Endpoint

| Action | Méthode | URL | Permission |
|--------|---------|-----|------------|
| register | POST | `/api/register/` | `AllowAny` (seul endpoint métier ouvert sans authentification) |

Action unique : **pas de ViewSet ni de router** ici (le skill `drf-resource` décrit un CRUD complet, qui ne s'applique pas). Une `CreateAPIView` + un `path()` explicite dans `accounts/urls.py`, inclus sous `/api/` dans les urls racine. Aucune route de lecture/modification/suppression de compte n'est exposée.

## 3. Champs en entrée

| Champ | Obligatoire | Contraintes |
|-------|-------------|-------------|
| `username` | oui | non vide, `max_length=150` (contrainte `AbstractUser`), unique, caractères validés par le `UnicodeUsernameValidator` de Django |
| `email` | oui | format email valide, unique |
| `password` | oui | write-only, validé par `AUTH_PASSWORD_VALIDATORS` |
| `password_confirm` | oui | write-only, doit être identique à `password` |

**Impact sur le modèle `accounts.User`** : `AbstractUser.email` est `blank=True` et sans contrainte d'unicité. Le champ est donc **surchargé** :

```
email = models.EmailField(unique=True)
```

`blank=False` étant le défaut, l'email devient **obligatoire et unique en base**, sans validation custom à écrire. Une migration accompagne ce changement. Aucun autre champ n'est ajouté à `User` (pas d'anticipation V2).

## 4. Validations

- **`username` unique** : contrainte du modèle, remontée automatiquement en 400 par le `ModelSerializer`.
- **`email` unique et de format valide** : le format est validé par `EmailField` ; l'unicité est garantie **en base** par `unique=True` sur `accounts.User.email` (cf. §3), et remontée automatiquement en 400 par le `ModelSerializer`. Aucune `validate_email()` custom n'est nécessaire.
- **`password`** : passé à `django.contrib.auth.password_validation.validate_password()` pour appliquer les `AUTH_PASSWORD_VALIDATORS` du projet. Les `ValidationError` de Django sont converties en `ValidationError` DRF → 400.
- **`password` == `password_confirm`** : vérifié dans `validate()` (règle inter-champs, pas un contrôle par champ). Erreur 400 sinon.
- **Mot de passe jamais stocké en clair** : la création passe **obligatoirement par `User.objects.create_user()`**, qui hashe via `set_password()`. **Ne jamais utiliser `User.objects.create()`** (qui écrirait le mot de passe en clair en base). `password_confirm` est retiré des données validées avant création.
- `password` et `password_confirm` sont `write_only` : ils ne peuvent jamais apparaître en réponse.
- **Fenêtre de course sur l'unicité** : le serializer vérifie l'unicité par un `SELECT`, mais une inscription concurrente peut insérer le même `username`/`email` entre ce `SELECT` et l'`INSERT`. La base refuse alors (contrainte `unique`) en levant une `IntegrityError`, qui doit être **rattrapée dans la vue et renvoyée en 400**, de la même forme que les autres erreurs de validation — jamais en 500. L'insertion est encadrée par un `transaction.atomic()` (savepoint), sans lequel la transaction courante resterait inutilisable après l'erreur.
  - L'erreur est **attribuée au(x) champ(s) réellement en conflit** (relecture en base après l'échec), pas supposée porter sur l'email : un conflit sur `username` doit renvoyer une erreur sur `username`, et un double conflit doit remonter les deux.
  - **La relecture doit se faire sur les valeurs normalisées** — c'est-à-dire celles réellement écrites en base. `create_user()` normalise **les deux champs** avant l'`INSERT` : `normalize_email()` (domaine en minuscules) **et** `normalize_username()` (Unicode NFKC). L'`UniqueValidator`, lui, interroge la base avec les valeurs brutes. Relire les valeurs brutes reviendrait à chercher ce que la base ne contient pas : le conflit serait manqué et l'`IntegrityError` remonterait en 500.
  - Corollaire : ces divergences se déclenchent **sans aucune concurrence**. `aude@EXAMPLE.COM` face à un `aude@example.com` existant, ou `ａｕｄｅ` (pleine chasse, replié en `aude` par NFKC) face à un `aude` existant : le `SELECT` de validation ne voit pas le doublon, mais l'`INSERT` normalisé le heurte. Ces cas passent par le même rattrapage et doivent renvoyer **400**, pas 500. Le `UnicodeUsernameValidator` ne les filtre pas (`\w` accepte ces caractères).
  - Si aucun conflit d'unicité n'explique l'`IntegrityError`, elle est **laissée remonter** : une erreur sans rapport doit rester une 500 visible plutôt que d'être maquillée en 400 trompeuse.

> **Décidé (2026-07-14) — unicité de l'email garantie en base.**
> `AbstractUser.email` n'a pas de contrainte `unique` par défaut. Le champ est donc **surchargé** sur `accounts.User` (cf. §3) plutôt que vérifié dans une `validate_email()` : une validation serializer seule laisserait une fenêtre de concurrence (deux inscriptions simultanées avec le même email pourraient passer toutes les deux). Cohérent avec l'`unique_together` de `Project`, où la contrainte est également portée par la base.

## 5. Réponse en succès (201)

```json
{
  "user": {
    "id": 1,
    "username": "aude",
    "email": "aude@example.com"
  },
  "access": "<jwt access token>",
  "refresh": "<jwt refresh token>"
}
```

- **Jamais** de `password`, ni en clair ni sous forme de hash, dans la réponse.
- Tokens générés via `RefreshToken.for_user(user)` (`rest_framework_simplejwt.tokens`), cohérent avec ce que produit déjà `/api/token/`.

## 6. Cas limites à couvrir (tests)

**Succès**
- Inscription valide → **201** ; `access` et `refresh` présents et **réellement utilisables** (vérifier que le token `access` authentifie une requête, ex. sur `/api/projects/`).
- La réponse ne contient **ni `password` ni `password_confirm`**, à aucun niveau.
- **En base, le mot de passe est hashé** : `user.password != "<mot de passe en clair envoyé>"` **et** `user.check_password("<clair>")` est vrai. Ce test est le garde-fou contre un `create()` employé par erreur à la place de `create_user()`.

**Erreurs → 400**
- `username` déjà pris.
- `email` déjà pris.
- **`email` déjà pris via la fenêtre de course** : validation du serializer contournée (l'unicité n'est pas vue au `SELECT`), l'`IntegrityError` de l'`INSERT` doit produire un **400** portant sur `email`, et non une 500. À tester en neutralisant l'`UniqueValidator` le temps de la requête, l'utilisateur existant bel et bien en base — sinon on ne teste que le cas déjà couvert par la validation.
- **`username` déjà pris via la fenêtre de course** → 400 portant sur `username`, **sans** mention d'`email` (vérifie l'attribution du bon champ).
- **Les deux champs en conflit** → 400 remontant `username` **et** `email`.
- **`email` ne différant que par la casse du domaine** (`aude@EXAMPLE.COM` vs `aude@example.com` existant) → **400** portant sur `email`.
- **`username` ne différant que par la normalisation NFKC** (`ａｕｄｅ` en pleine chasse vs `aude` existant) → **400** portant sur `username`.
  Ces deux cas ne nécessitent **aucun mock** : ils traversent réellement le rattrapage d'`IntegrityError` et gardent contre une relecture faite sur les valeurs non normalisées. Le second est le pendant exact du premier — corriger l'un sans l'autre laisse une 500 ouverte.
- `email` mal formé (ex. `"pas-un-email"`).
- `password` ≠ `password_confirm`.
- Mot de passe trop faible — **un cas par validateur actif** dans `AUTH_PASSWORD_VALIDATORS` :
  - trop court (`MinimumLengthValidator`),
  - trop commun (`CommonPasswordValidator`, ex. `"password"`),
  - uniquement numérique (`NumericPasswordValidator`),
  - trop proche du `username` (`UserAttributeSimilarityValidator`).
- Champ obligatoire manquant : un cas par champ (`username`, `email`, `password`, `password_confirm`).

Dans **tous** les cas d'erreur, vérifier qu'**aucun utilisateur n'a été créé** en base.

## 7. Hors scope

- **Vérification de l'email** (envoi d'un lien de confirmation, compte inactif tant que non vérifié).
- **Connexion via réseaux sociaux** (OAuth, etc.).
- **Récupération de mot de passe oublié** (reset par email).
- Modification/suppression du compte, changement de mot de passe : non exposés par cette spec.
- Rate limiting / anti-abus sur l'inscription : non traité en V1.
- **Normalisation de la partie locale de l'email** : `normalize_email()` ne minusculise que le domaine. `AUDE@example.com` et `aude@example.com` sont donc considérés comme deux emails distincts et créent deux comptes. Choix assumé (comportement par défaut de Django) ; non traité en V1.
- **V2 / collaboratif** : aucun rôle, aucune invitation.
