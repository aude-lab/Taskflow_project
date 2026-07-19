from unittest import mock

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.validators import UniqueValidator

from .models import User

VALID_PASSWORD = "Brouillard-Tuile-42"


class RegisterAPITestCase(APITestCase):
    """Tests de l'inscription (cf. accounts/SPEC.md)."""

    def setUp(self):
        self.url = reverse("register")

    def payload(self, **overrides):
        data = {
            "username": "aude",
            "email": "aude@example.com",
            "password": VALID_PASSWORD,
            "password_confirm": VALID_PASSWORD,
        }
        data.update(overrides)
        return data

    # --- Succès ---

    def test_register_returns_201_with_user_and_tokens(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["username"], "aude")
        self.assertEqual(response.data["user"]["email"], "aude@example.com")
        self.assertIn("id", response.data["user"])
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(User.objects.filter(username="aude").exists())

    def test_response_never_exposes_password(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Ni en clair, ni sous forme de hash, à aucun niveau de la réponse.
        body = str(response.data)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_confirm", response.data)
        self.assertNotIn("password", response.data["user"])
        self.assertNotIn(VALID_PASSWORD, body)
        self.assertNotIn(User.objects.get(username="aude").password, body)

    def test_password_is_hashed_in_database(self):
        # Garde-fou anti-`User.objects.create()` : si create_user() était
        # remplacé par create(), le mot de passe serait stocké en clair.
        self.client.post(self.url, self.payload(), format="json")
        user = User.objects.get(username="aude")
        self.assertNotEqual(user.password, VALID_PASSWORD)
        self.assertTrue(user.check_password(VALID_PASSWORD))

    def test_returned_refresh_token_is_usable(self):
        # SPEC §6 : les tokens doivent être « réellement utilisables », pas
        # seulement présents.
        response = self.client.post(self.url, self.payload(), format="json")
        refreshed = self.client.post(
            reverse("token_refresh"),
            {"refresh": response.data["refresh"]},
            format="json",
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertIn("access", refreshed.data)

    def test_returned_access_token_authenticates_a_request(self):
        response = self.client.post(self.url, self.payload(), format="json")
        access = response.data["access"]
        projects_url = reverse("project-list")
        # Sans token : refusé.
        self.assertEqual(
            self.client.get(projects_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        # Avec le token issu de l'inscription : accepté.
        authenticated = self.client.get(
            projects_url, HTTP_AUTHORIZATION=f"Bearer {access}"
        )
        self.assertEqual(authenticated.status_code, status.HTTP_200_OK)

    # --- Unicité ---

    def test_duplicate_username_rejected(self):
        self.client.post(self.url, self.payload(), format="json")
        response = self.client.post(
            self.url,
            self.payload(email="autre@example.com"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_email_rejected(self):
        self.client.post(self.url, self.payload(), format="json")
        response = self.client.post(
            self.url, self.payload(username="autre"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

    def test_email_race_condition_returns_400(self):
        # Fenêtre de course : le serializer interroge la base (SELECT) et ne voit
        # aucun doublon, puis l'INSERT se heurte à la contrainte d'unicité. On
        # simule ce cas en neutralisant l'UniqueValidator de DRF le temps de la
        # requête — l'utilisateur, lui, existe bel et bien en base.
        self.client.post(self.url, self.payload(), format="json")
        with mock.patch.object(UniqueValidator, "__call__", return_value=None):
            response = self.client.post(
                self.url, self.payload(username="autre"), format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(User.objects.count(), 1)

    def test_email_domain_case_variant_returns_400(self):
        # create_user() normalise le domaine en minuscules, alors que
        # l'UniqueValidator interroge la base avec la valeur brute : le SELECT ne
        # voit pas le doublon, mais l'INSERT écrit la valeur normalisée et se
        # heurte à la contrainte. Pas besoin de concurrence pour déclencher ce
        # cas — il suffit de taper son domaine en majuscules.
        self.client.post(self.url, self.payload(), format="json")
        response = self.client.post(
            self.url,
            self.payload(username="autre", email="aude@EXAMPLE.COM"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(User.objects.count(), 1)

    def test_username_unicode_variant_returns_400(self):
        # Pendant du cas email : create_user() normalise aussi le username
        # (NFKC) avant l'INSERT. « ａｕｄｅ » en pleine chasse se replie sur
        # « aude » et passe le UnicodeUsernameValidator (\w les accepte). Sans
        # relecture normalisée, l'IntegrityError remonterait en 500.
        self.client.post(self.url, self.payload(), format="json")
        response = self.client.post(
            self.url,
            self.payload(username="ａｕｄｅ", email="autre@example.com"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertEqual(User.objects.count(), 1)

    def test_username_race_condition_attributed_to_username(self):
        # SPEC §4 : l'erreur doit porter sur le champ réellement en conflit —
        # ici username, et surtout pas email.
        self.client.post(self.url, self.payload(), format="json")
        with mock.patch.object(UniqueValidator, "__call__", return_value=None):
            response = self.client.post(
                self.url,
                self.payload(email="autre@example.com"),
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertNotIn("email", response.data)
        self.assertEqual(User.objects.count(), 1)

    def test_race_condition_on_both_fields_reports_both(self):
        self.client.post(self.url, self.payload(), format="json")
        with mock.patch.object(UniqueValidator, "__call__", return_value=None):
            response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)
        self.assertEqual(User.objects.count(), 1)

    # --- Format & correspondance ---

    def test_malformed_email_rejected(self):
        response = self.client.post(
            self.url, self.payload(email="pas-un-email"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    def test_password_mismatch_rejected(self):
        response = self.client.post(
            self.url,
            self.payload(password_confirm="Autre-Chose-99"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    # --- Un cas par validateur de AUTH_PASSWORD_VALIDATORS ---

    def assertRejectedOnPassword(self, response):
        # L'erreur doit porter sur `password` : sans cette assertion, une
        # régression échouant pour un autre motif (username invalide, etc.)
        # laisserait le test vert.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.exists())

    def test_password_too_short_rejected(self):
        # MinimumLengthValidator
        response = self.client.post(
            self.url,
            self.payload(password="Ab1!", password_confirm="Ab1!"),
            format="json",
        )
        self.assertRejectedOnPassword(response)

    def test_common_password_rejected(self):
        # CommonPasswordValidator
        response = self.client.post(
            self.url,
            self.payload(password="password", password_confirm="password"),
            format="json",
        )
        self.assertRejectedOnPassword(response)

    def test_numeric_password_rejected(self):
        # NumericPasswordValidator
        response = self.client.post(
            self.url,
            self.payload(password="8461937205", password_confirm="8461937205"),
            format="json",
        )
        self.assertRejectedOnPassword(response)

    def test_password_too_similar_to_username_rejected(self):
        # UserAttributeSimilarityValidator : ne se déclenche que si une instance
        # User est passée à validate_password().
        response = self.client.post(
            self.url,
            self.payload(
                username="brouillard",
                password="brouillard",
                password_confirm="brouillard",
            ),
            format="json",
        )
        self.assertRejectedOnPassword(response)

    # --- Champs obligatoires manquants ---

    def test_missing_username_rejected(self):
        payload = self.payload()
        del payload["username"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    def test_missing_email_rejected(self):
        payload = self.payload()
        del payload["email"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    def test_missing_password_rejected(self):
        payload = self.payload()
        del payload["password"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    def test_missing_password_confirm_rejected(self):
        payload = self.payload()
        del payload["password_confirm"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())


class LoginLogoutViewTestCase(TestCase):
    """Tests connexion/déconnexion du front (cf. core/SPEC-front-base.md)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="aude", email="aude@example.com", password=VALID_PASSWORD
        )
        self.login_url = reverse("login")
        self.logout_url = reverse("logout")

    def test_login_page_renders(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            self.login_url,
            {"username": "aude", "password": VALID_PASSWORD},
        )
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_with_invalid_credentials(self):
        response = self.client.post(
            self.login_url, {"username": "aude", "password": "mauvais-mdp"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_user_redirected_away_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(self.login_url)
        self.assertRedirects(response, reverse("home"))

    def test_logout_via_post(self):
        self.client.force_login(self.user)
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, self.login_url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_via_get_is_rejected(self):
        # Depuis Django 5, LogoutView n'accepte que POST : un lien <a> vers
        # cette URL donnerait 405. La navigation utilise donc un formulaire.
        self.client.force_login(self.user)
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


class RegistrationViewTestCase(TestCase):
    """Tests de l'inscription depuis le front (cf. core/SPEC-front-base.md)."""

    def setUp(self):
        self.url = reverse("registration")

    def payload(self, **overrides):
        data = {
            "username": "aude",
            "email": "aude@example.com",
            "password1": VALID_PASSWORD,
            "password2": VALID_PASSWORD,
        }
        data.update(overrides)
        return data

    def assertRejected(self, response):
        """Formulaire réaffiché avec erreur, et aucun utilisateur créé."""
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_registration_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/registration.html")

    def test_valid_registration_creates_and_logs_in(self):
        response = self.client.post(self.url, self.payload())
        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(username="aude")
        self.assertEqual(user.email, "aude@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_password_is_hashed_in_database(self):
        # Même garde-fou que côté API : le mot de passe ne doit jamais être
        # stocké en clair.
        self.client.post(self.url, self.payload())
        user = User.objects.get(username="aude")
        self.assertNotEqual(user.password, VALID_PASSWORD)
        self.assertTrue(user.check_password(VALID_PASSWORD))

    def test_duplicate_username_rejected(self):
        User.objects.create_user(
            username="aude", email="autre@example.com", password=VALID_PASSWORD
        )
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200)
        # Sur le bon champ : sans cette précision, le test passerait si l'erreur
        # remontait ailleurs.
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_email_rejected(self):
        User.objects.create_user(
            username="autre", email="aude@example.com", password=VALID_PASSWORD
        )
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_form_errors_are_rendered_in_html(self):
        # Les erreurs doivent être VISIBLES, pas seulement présentes dans
        # form.errors : un template qui cesserait de les rendre passerait
        # inaperçu (Django n'échoue pas sur une variable manquante).
        response = self.client.post(self.url, self.payload(email=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "text-danger")

    def test_login_error_is_rendered_in_html(self):
        response = self.client.post(
            reverse("login"), {"username": "inconnu", "password": "x"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alert-danger")

    def test_password_mismatch_rejected(self):
        response = self.client.post(
            self.url, self.payload(password2="Autre-Chose-99")
        )
        self.assertRejected(response)

    def test_weak_password_rejected(self):
        response = self.client.post(
            self.url, self.payload(password1="password", password2="password")
        )
        self.assertRejected(response)

    def test_missing_email_rejected(self):
        response = self.client.post(self.url, self.payload(email=""))
        self.assertRejected(response)

    def test_authenticated_user_redirected_away_from_registration(self):
        user = User.objects.create_user(
            username="deja", email="deja@example.com", password=VALID_PASSWORD
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("home"))
