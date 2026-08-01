#!/bin/bash
# Étape de build Vercel (static-build) : installe les dépendances et rassemble
# les fichiers statiques dans STATIC_ROOT (staticfiles_build/static), servi
# ensuite via la route /static/ de vercel.json.
# --break-system-packages : l'image de build Vercel a un Python « externally
# managed » (PEP 668) qui refuse pip sans ce drapeau. Sans effet ailleurs ;
# le conteneur de build est éphémère.
python3 -m pip install --break-system-packages -r requirements.txt
python3 manage.py collectstatic --noinput --clear
