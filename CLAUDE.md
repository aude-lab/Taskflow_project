# CLAUDE.md — TaskFlow

Mémoire permanente du projet. À lire au début de chaque session et avant d'écrire chaque ligne de code.

## Contexte & objectif d'apprentissage

TaskFlow est une application web de gestion de projets et de tâches, réalisée en solo par Aude (étudiante ingénieur, EPITA M1), à Paris en 2026.

**L'objectif premier est l'apprentissage, pas la vitesse de livraison.** Il s'agit de comprendre en profondeur Django/DRF et une méthode de développement structurée avec un agent IA. Le code est écrit avec Claude Code, mais **la conception, les choix d'architecture et la validation des étapes appartiennent à Aude**. Privilégier les explications et la compréhension à chaque étape.

## Objectif fonctionnel (V1 — version actuelle)

Application mono-utilisatrice permettant de créer des projets, y ajouter des tâches, suivre leur avancement (statut, priorité, échéance) et visualiser l'ensemble via un tableau de bord avec filtres.

Périmètre V1 :
- Authentification (inscription, connexion, déconnexion, gestion du compte)
- CRUD projets
- CRUD tâches (rattachées à un projet ; champs : titre, description, priorité basse/moyenne/haute, statut à faire/en cours/terminé, date d'échéance)
- Tableau de bord (tâches en retard, à venir, par statut)
- Filtres (par projet, statut, priorité, échéance)
- Admin Django native (exploration/debug en dev)

> **V2 (collaboratif : plusieurs utilisateurs, rôles owner/membre) n'existe pas encore.** Ne rien anticiper de la V2 dans le code de la V1.

## Stack technique

- **Langage** : Python
- **Framework** : Django
- **API** : Django REST Framework (DRF)
- **Base de données** : PostgreSQL
- **Frontend** : HTML / CSS / Bootstrap (templates Django)
- **Versionning** : Git

## Architecture (apps Django)

- `accounts` — utilisateur, authentification
- `projects` — modèle `Project` et son CRUD
- `tasks` — modèle `Task` et son CRUD (priorité, statut, échéance)
- `core` — utilitaires partagés (permissions custom, mixins, etc.)

Entités principales (sujet à affinage) :
- `User` — authentification Django (éventuellement étendue)
- `Project` — nom, description, propriétaire (User), date de création
- `Task` — titre, description, statut, priorité, date d'échéance, projet parent (Project)

## Conventions de code

- Respecter les conventions Django/DRF idiomatiques (structure d'app standard, noms explicites).
- Code Python conforme à PEP 8.
- Une app = une responsabilité ; mettre le code réellement partagé dans `core`, pas ailleurs.
- Écrire dans la même langue et le même style que le code environnant.
- Chaque fonctionnalité s'accompagne de tests.
- Valeurs stockées des `choices` (status, priority, etc.) : toujours en ASCII sans accents (ex. `a_faire`, `termine`). Le libellé accentué va uniquement dans le second élément du choice, pour l'affichage.

## Méthode de travail (obligatoire)

1. **Spec avant code.** Avant toute nouvelle fonctionnalité, rédiger un `SPEC.md` court (objectif, périmètre, modèles/endpoints concernés, cas limites) et **le faire valider par Aude avant d'écrire la moindre ligne de code**.
2. **Plan avant édition.** Toujours proposer un plan (fichiers touchés, étapes) et attendre l'accord avant d'éditer des fichiers.
3. **Pas de « terminé » sans preuve.** Ne jamais annoncer une tâche finie sans preuve : les tests correspondants passent, sortie à l'appui.
4. **Relecture avant clôture.** Faire relire le diff par un subagent reviewer avant de clore une tâche.
5. **Incrémental.** La V1 doit être complète et fonctionnelle avant d'aborder la V2.

## Standard de qualité attendu

Le code doit être **professionnel et prêt pour un vrai usage**, pas un prototype minimal : gestion des erreurs et des cas limites, validations correctes côté serializer, requêtes ORM efficaces (éviter les N+1 queries), tests couvrant les cas nominaux et les cas limites.

« Simple » ne veut pas dire « pauvre » : ça veut dire ne pas ajouter de complexité qui ne sert à rien maintenant (cf. ci-dessous), pas ne pas gérer les erreurs ou bâcler la validation.

## À éviter

- **La sur-ingénierie** : ne pas ajouter d'abstractions, de couches génériques ou d'options configurables qui ne répondent à aucun besoin actuel de la V1. Le code doit rester simple à lire, pas simpliste dans sa robustesse.
- **Anticiper la V2** : aucun champ, aucun rôle « au cas où » pour le collaboratif. On code pour la V1 solo.
- **Sortir du périmètre** : ne pas modifier de fichiers hors du scope de la tâche en cours ; ne pas faire de refactoring opportuniste non demandé.
- **Sauter les étapes de la méthode** (spec, plan, tests, relecture).
