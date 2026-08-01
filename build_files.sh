#!/bin/bash
# Étape de build Vercel (static-build) : installe les dépendances et rassemble
# les fichiers statiques dans STATIC_ROOT (staticfiles_build/static), servi
# ensuite via la route /static/ de vercel.json.
python3 -m pip install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
