# SPEC — Front : polish visuel

## 1. Objectif

Améliorer la lisibilité du front (Bootstrap, sans refonte) sur quatre axes validés : badges de couleur statut/priorité, mise en évidence des retards, navigation active + cohérence, états vides plus soignés. **Aucun changement de comportement fonctionnel.**

## 2. Badges statut / priorité

Statut et priorité s'affichent en **pastilles Bootstrap colorées** au lieu de texte brut, partout où ils apparaissent (liste filtrable des tâches, détail projet, dashboard).

Palette (classique) :

| Statut | Classe | | Priorité | Classe |
|--------|--------|---|----------|--------|
| À faire | `text-bg-secondary` | | Basse | `text-bg-secondary` |
| En cours | `text-bg-primary` | | Moyenne | `text-bg-warning` |
| Terminé | `text-bg-success` | | Haute | `text-bg-danger` |

**Mécanique (source unique, DRY)** : un module de *template tags* `tasks/templatetags/task_badges.py` fournit `{% status_badge value %}` et `{% priority_badge value %}`, rendus par un partial `tasks/templates/tasks/_badge.html` (`<span class="badge text-bg-…">Libellé</span>`). Le libellé vient du modèle (`Task.Status(value).label`) — jamais recopié ; la couleur d'un mapping. Un statut/priorité inconnu retombe sur `secondary` (pas d'erreur).

## 3. Mise en évidence des retards

Une tâche **en retard** (`due_date < aujourd'hui` **ET** `status != termine`) voit son échéance **en rouge** dans les listes (liste filtrable, détail projet).

- Un filtre de template `{% if task|is_overdue %}` (même module) encapsule la règle : `due_date` non nul, `< timezone.localdate()`, statut ≠ terminé. `aujourd'hui` reste calculé côté serveur.
- Le dashboard a déjà son encadré « En retard » (bordure rouge) — inchangé.

## 4. Navigation active + cohérence

- Dans `base.html`, le lien de la **section courante** porte la classe `active` (Projets si l'URL est sous `/projets/`, Tâches si sous `/taches/`).
- Harmonisation légère : titres de page, marges, et les tableaux de tâches (détail projet, dashboard, liste) utilisent les mêmes badges.

## 5. États vides plus soignés

Les « Aucune tâche… » passent d'une ligne de tableau grise à un **encart centré** (`text-center text-muted`, marge verticale), avec le cas échéant un bouton d'action (ex. « Nouvelle tâche » sur un projet vide). Les deux messages distincts de la liste filtrable (« aucune tâche » / « aucun résultat pour ces filtres ») sont conservés.

## 6. Sécurité / périmètre

- **Aucune logique métier touchée** : présentation uniquement. `is_overdue` réutilise la même règle que le dashboard (pas une seconde définition du « retard » côté données — c'est un helper d'affichage).
- Pas de nouvelle dépendance (Bootstrap déjà en CDN ; pas d'icônes externes — un emoji discret au plus).
- Pas de changement d'URL, de vue (au sens données), de modèle, de migration.

## 7. Tests

Présentation, donc tests ciblés (`assertContains`) :

- Une tâche `haute` rend `text-bg-danger` ; `terminé` rend `text-bg-success` (badge couleur correct).
- Le libellé accentué reste présent (« Haute », « Terminé »), jamais la valeur ASCII.
- Une tâche en retard rend l'échéance en `text-danger` ; une tâche à échéance future ou terminée ne l'a pas (le filtre `is_overdue` mord).
- Le lien de nav de la section courante porte `active`.
- État vide : l'encart soigné est rendu (pas la ligne de tableau).
- **Non-régression** : les 180 tests existants passent (les assertions de libellés « En cours »/« Terminé » restent valides puisque les libellés demeurent).

## 8. Hors scope

- Thème sombre, CSS custom lourd, icônes externes, refonte de mise en page.
- Coloration des cartes de compteurs du dashboard (on garde les compteurs neutres pour l'instant).
- V2.
