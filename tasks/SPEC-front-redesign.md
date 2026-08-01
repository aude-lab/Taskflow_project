# SPEC — Refonte visuelle du front (design Stitch / Tailwind)

## 1. Objectif & périmètre

Remplacer l'habillage Bootstrap actuel par le design produit dans `maquette/`
(4 écrans Tailwind, style « Material 3 » accent indigo). **On ne touche ni au
back, ni aux endpoints, ni au comportement** : mêmes routes, mêmes données,
même JS fonctionnel (génération IA, chat, filtres, auth). C'est une refonte de
présentation, pas de logique.

Contrainte projet forte (`CLAUDE.md`) : **rester en V1 solo**. La maquette
contient beaucoup d'éléments d'un produit d'équipe (V2) — ils sont retirés
(cf. §5).

## 2. Décisions validées

- **Tailwind fidèle, via CDN** (`cdn.tailwindcss.com`) + config inline reprise
  de la maquette (palette, radius, spacing, fonts, fontSizes). On quitte
  Bootstrap.
- **Rester V1** : on retire membres/collaborateurs/assignés, recherche globale,
  notifications, page Paramètres, barre de progression %, IDs de tâches
  (TSK-104), catégories, badges « IA active », mentions « Senior Dev / équipe ».
- **Page chat** : `maquette/assistantiapage.html` (le bon fichier, distinct du
  dashboard) sert de base à `/assistant/`.

## 3. Fondation technique

- **Nouveau `core/templates/base.html`** portant le *shell* commun (sidebar +
  top-bar + zone contenu + bouton IA flottant + nav mobile). Toutes les pages
  authentifiées en héritent via `{% block content %}`.
- Dans `<head>` : Tailwind CDN, `tailwind.config` inline (identique à la
  maquette), Google Fonts (Geist, JetBrains Mono), Material Symbols, et le bloc
  `<style>` custom (`glass-card`, `ai-card`/`ai-glow`, `status-pill`,
  `loading-dots`…). Un `{% block extra_head %}` et un `{% block extra_js %}`
  permettent aux pages d'ajouter leur CSS/JS.
- **Bootstrap est retiré** (CSS + JS + toutes les classes `btn/card/badge/...`
  dans les templates migrés).
- **Assets externes retirés** : les images hébergées par Google (avatars, logo
  placeholder) ne sont pas conservées. Le logo = texte « TaskFlow » (+ éventuel
  `core/logo.png` local déjà présent). Les avatars deviennent l'**initiale** de
  l'utilisateur dans une pastille (pas de photo).
- **Layout d'authentification distinct** : login / inscription n'ont pas la
  sidebar (utilisateur non connecté). Un `{% block %}` ou un mini-layout centré
  est prévu pour ces pages.

> Dépendance runtime assumée : Tailwind CDN affiche un avertissement console
> « not for production ». Acceptable pour ce projet d'apprentissage (décision
> « Tailwind fidèle »). Une variante compilée pourra venir plus tard.

## 4. Shell global (mapping vers l'existant)

**Sidebar** (nav principale) → routes réelles :
| Item | Icône | Route |
|------|-------|-------|
| Tableau de bord | `dashboard` | `home` |
| Projets | `folder` | `project_list` |
| Assistant IA | `smart_toy` | `assistant` |
| Tâches | `checklist` | `task_list` |

- L'item actif est déterminé par le nom d'URL courant (comme aujourd'hui).
- **« Paramètres » retiré** (pas de page settings en V1).
- **Bouton CTA bas de sidebar** : « Nouveau projet » → `project_create` (un
  « Nouvelle tâche » global n'a pas de sens : une tâche exige un projet parent).

**Top-bar** :
- Recherche globale **retirée** (V2).
- Cloche notifications **retirée** (V2).
- Bloc utilisateur : `{{ user.username }}` + **déconnexion** (form POST vers
  `logout`, comme l'actuel), avatar = initiale.

**Bouton IA flottant** → lien vers `assistant`.
**Nav mobile (bas)** : mêmes 4 entrées que la sidebar.

## 5. Écran par écran

Pour chaque écran : on garde la structure visuelle de la maquette, on branche
les vraies données, on retire le V2, on **préserve les hooks JS existants**
(mêmes `id`).

### 5.1 Tableau de bord (`core/templates/core/home.html`)
- **Compteurs par statut** (À faire / En cours / Terminé) ← `by_status_display`.
- **2 cartes d'action** : « Commencer avec l'assistant IA » → `assistant` ;
  « Créer un projet manuellement » → `project_create`.
- **En retard** ← `overdue` ; **À venir (14 j)** ← `upcoming`.
- Retirer : IDs de tâches, « Depuis 2j », colonnes projet fictives, statuts
  inventés (« Programmé »…). Afficher les vrais champs (titre, priorité,
  échéance, statut). Le retard reste en rouge (`is_overdue`).

### 5.2 Mes projets (`projects/templates/projects/project_list.html`)
- Grille de **cartes projet** : nom, description (tronquée), **nombre de
  tâches** ← `task_count`, actions **Ouvrir** (`project_detail`) / **Modifier**
  (`project_update`) / **Supprimer** (`project_delete`).
- Carte « + Créer un nouveau projet » → `project_create`.
- Retirer : avatars de membres, badges « IA active », compteurs fictifs.

### 5.3 Détail projet (`projects/templates/projects/project_detail.html`)
- En-tête : nom, dates, **Modifier** / **Supprimer**, retour à `project_list`.
- **Section Assistant IA** conservée fonctionnellement : bouton « Réajuster avec
  l'IA » (→ `assistant?project_id=<pk>`), zone « Générer des tâches » (textarea
  + bouton + aperçu à cases à cocher). **On garde les `id` du JS** (`#ai-toggle`,
  `#ai-text`, `#ai-analyze`, `#ai-preview`, `#ai-preview-list`, `#ai-create`,
  `#ai-message`) — seul l'habillage change.
- **Tableau des tâches** : Titre, Statut, Priorité, Échéance (rouge si
  dépassée), Actions (Modifier/Supprimer).
- Retirer : barre de progression %, « Membres du projet », « Assigné à », filtre
  local (les filtres vivent sur `/taches/`).

### 5.4 Assistant chat (`core/templates/core/assistant.html`)
- **Fil de bulles** (assistant à gauche, utilisateur à droite), **indicateur de
  saisie** (`loading-dots`), **carte « Plan proposé »** (nom projet + tâches +
  boutons **Confirmer et créer** / continuer), **barre d'input** fixe.
- **On garde le contrat JS existant** (`#assistant[data-project-id]`,
  `#chat-log`, `#chat-form`, `#chat-input`, `#send-btn`, `#chat-error`,
  `#proposal`, `#proposal-project`, `#proposal-desc`, `#proposal-tasks`,
  `#confirm-btn`) : je réécris le markup autour, la logique `fetch` (chat →
  projects → confirm → redirect) est inchangée.
- Retirer : bouton pièce jointe (`attach_file`, pas d'upload), ton « équipe ».
  Le message d'accueil reste généré côté JS (nouveau projet vs réajustement).

## 6. Pages sans maquette (restylées pour cohérence)

Elles n'ont pas de maquette mais doivent rester fonctionnelles et cohérentes :
- **Login / Inscription** (`accounts/templates/accounts/*`) : layout centré sans
  sidebar, style Tailwind.
- **Liste des tâches** (`tasks/templates/tasks/task_list.html`) avec ses
  **filtres** (projet/statut/priorité/échéance) — comportement GET inchangé,
  habillage Tailwind (form + tableau).
- **Formulaires** tâche/projet (`*_form.html`) et **confirmations de
  suppression** (`*_confirm_delete.html`) : cartes + champs Tailwind (plugin
  `forms` déjà chargé par le CDN).
- **Messages Django** (`messages`) : re-stylés en alerts Tailwind (succès /
  erreur), en conservant `alert-<tag>` **ou** en adaptant les tests (cf. §8).
- Partiels `core/_task_table.html`, `tasks/_task_table.html`, `tasks/_badge.html`.

## 7. Fonctionnel à préserver (non négociable)

- JS **génération/confirmation** (détail projet) : fetch `generate`/`confirm`,
  CSRF, aperçu à cases, reload.
- JS **chat** (`/assistant/`) : historique, `POST /api/chat/`, rendu proposal,
  confirmation (projects + confirm) + redirect.
- **Filtres** de la liste des tâches (form GET + `TaskFilter`).
- **Auth** (login/logout/inscription), **messages** de succès/erreur.
- Comportement d'isolation (un utilisateur ne voit que ses données) — inchangé.

## 8. Impact tests & badges (à traiter en lockstep)

Le redesign casse des tests qui assertent du **markup Bootstrap**. À mettre à
jour pour viser le **nouveau markup**, sans changer l'intention testée :
- `tasks/templatetags/task_badges.py` : `STATUS_BADGE` / `PRIORITY_BADGE`
  renvoient des couleurs Bootstrap (`secondary/primary/success/warning/danger`)
  et `_badge.html` utilise `text-bg-*`. → Remplacer par des classes de pastille
  Tailwind (ex. mapping statut/priorité → couleurs `surface-*`, `secondary`,
  `error`…).
- Tests couplés au markup, à adapter : `tasks/tests.py` (`text-bg-success`,
  `text-bg-danger`, `text-center text-muted`, navbar `nav-link active`),
  `projects/tests.py` (`text-danger`), `accounts/tests.py` (`text-danger`,
  `alert-danger`), tests navbar de `core`/`tasks`.
- Les tests **de contenu** (libellés, messages, isolation, présence d'un titre)
  restent valables tels quels.
- Objectif inchangé : **toute la suite au vert** à la fin (les assertions de
  markup pointent le nouveau habillage, la couverture fonctionnelle est
  conservée).

## 9. Hors scope

- Toute fonctionnalité V2 (équipe, rôles, assignation, recherche globale,
  notifications, paramètres, progression).
- Dark mode (la maquette a des variantes `dark:` ; non requis — on livre le
  thème clair, on ne s'interdit pas de garder les classes `dark:` inertes).
- Refonte back / nouveaux endpoints / nouveaux champs.
- Tailwind compilé en local (build Node) — éventuelle amélioration ultérieure.

## 10. Fichiers touchés & phasage

**Base & shell**
- `core/templates/base.html` (réécrit : shell Tailwind + blocks).

**Écrans avec maquette**
- `core/templates/core/home.html`
- `projects/templates/projects/project_list.html`
- `projects/templates/projects/project_detail.html` (markup + JS conservé)
- `core/templates/core/assistant.html` (markup + JS conservé)

**Écrans sans maquette (cohérence)**
- `accounts/templates/accounts/login.html`, `registration.html`
- `tasks/templates/tasks/task_list.html`, `task_form.html`,
  `task_confirm_delete.html`, `_task_table.html`, `_badge.html`
- `projects/templates/projects/project_form.html`,
  `project_confirm_delete.html`
- `core/templates/core/_task_table.html`

**Logique d'affichage & tests**
- `tasks/templatetags/task_badges.py` (mapping couleurs → Tailwind)
- `tasks/tests.py`, `projects/tests.py`, `accounts/tests.py`, `core/tests.py`
  (assertions de markup mises à jour)

**Phasage proposé** (chaque phase testable) :
1. `base.html` (shell) + `home` — valide la direction visuelle.
2. `project_list` + `project_detail` (avec JS génération).
3. `assistant` (chat).
4. Pages secondaires (auth, task_list+filtres, forms, delete) + badges.
5. Mise à jour des tests → suite complète au vert + relecture.

> Le dossier `maquette/` reste une **référence** (non servi par Django). On peut
> le garder dans le repo ou le supprimer après migration — à décider en fin de
> chantier.
