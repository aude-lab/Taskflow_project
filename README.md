TaskFlow

Application web de gestion de projets et de tâches.
Projet personnel — Paris, 2026.

Contexte

Projet réalisé en solo par Aude, étudiante en cycle ingénieur (EPITA, niveau M1), dans un objectif d'apprentissage : comprendre en profondeur le framework Django/DRF ainsi qu'une méthode de développement structurée avec un agent IA (Claude Code). La priorité est la compréhension, pas la vitesse de livraison.

Le code lui-même est écrit avec Claude Code. La conception, les choix d'architecture et la validation des étapes sont faits par Aude, accompagnée pour les explications par Claude (claude.ai).

Objectif fonctionnel

Une application permettant de créer des projets, d'y ajouter des tâches, de suivre leur avancement (statut, priorité, échéance), et de visualiser l'ensemble via un tableau de bord avec filtres.

Versions

V1 — Version solo (version actuelle)

Une seule utilisatrice. Pas de partage, pas de rôles, pas de notion d'équipe.

V2 — Version collaborative (plus tard)

Plusieurs utilisateurs peuvent partager un même projet, avec des rôles (owner, membre). Cette version n'est pas anticipée dans le code de la V1.

Fonctionnalités prévues (V1)


Authentification : inscription, connexion, déconnexion, gestion du compte utilisateur.
Gestion des projets (CRUD) : créer, lister, modifier, supprimer un projet.
Gestion des tâches (CRUD) : créer, lister, modifier, supprimer une tâche, rattachée à un projet.

Champs clés d'une tâche : titre, description, priorité (basse/moyenne/haute), statut (à faire/en cours/terminé), date d'échéance.



Tableau de bord : vue d'ensemble des tâches et projets de l'utilisatrice (ex : tâches en retard, à venir, par statut).
Filtres avancés : filtrer les tâches par projet, statut, priorité, échéance.
Interface d'administration Django : gestion des données via l'admin natif, pour l'exploration et le debug en développement.


Stack technique


Langage : Python
Framework web : Django
API : Django REST Framework (DRF)
Base de données : PostgreSQL
Frontend : HTML / CSS / Bootstrap (rendu via templates Django)
Versionning : Git


Architecture (apps Django)


accounts — utilisateur, authentification
projects — modèle Project et son CRUD
tasks — modèle Task et son CRUD (priorité, statut, échéance)
core — utilitaires partagés entre apps (permissions custom, mixins, etc.)


Entités principales (aperçu, sujet à affinage)


User : géré par le système d'authentification Django (éventuellement étendu).
Project : nom, description, propriétaire (User), date de création.
Task : titre, description, statut, priorité, date d'échéance, projet parent (Project).


Méthode de développement


Développement guidé par spécification : avant chaque nouvelle fonctionnalité, rédaction d'un court document de spécification, validé avant l'implémentation.
Vérification systématique (tests) avant de considérer une tâche terminée.
Relecture du code produit avant validation finale.
Approche incrémentale : la V1 (solo) doit être complète et fonctionnelle avant d'attaquer la V2 (collaborative).


Statut actuel

Projet en tout début de conception. Aucun code écrit à ce jour. Étape en cours : mise en place de l'architecture et de la méthode de travail avec l'agent de développement (Claude Code).