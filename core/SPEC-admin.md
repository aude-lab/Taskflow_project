# SPEC — Configuration de l'admin Django

Configuration d'affichage de l'admin natif pour `User`, `Project` et `Task`
(exploration/debug en dev). **Aucune logique métier ici** : uniquement du
`list_display` / `list_filter` / `search_fields`. Chaque modèle est enregistré
dans l'`admin.py` de sa propre app.

## accounts/admin.py — User

- `list_display` : `username`, `email`, `is_staff`
- `search_fields` : `username`, `email`
- Enregistré via une **sous-classe de `django.contrib.auth.admin.UserAdmin`**
  (et non un `ModelAdmin` nu). Raison : `UserAdmin` fournit le formulaire de
  changement de mot de passe (hash géré correctement). Un `ModelAdmin` basique
  exposerait le champ `password` en clair et permettrait d'écrire un mot de
  passe non hashé — à éviter.

## projects/admin.py — Project

- `list_display` : `name`, `owner`, `created_at`
- `list_filter` : `owner`
- `search_fields` : `name`

## tasks/admin.py — Task

- `list_display` : `title`, `project`, `status`, `priority`, `due_date`
- `list_filter` : `status`, `priority`, `project`
- `search_fields` : `title`

## Hors scope

- Aucune action custom, aucun `readonly_fields`, aucune surcharge de
  `save_model` ni de queryset. Pas de logique métier.
- Pas d'anticipation V2.
