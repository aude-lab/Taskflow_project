"""
WSGI config for taskflow project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'taskflow.settings')

application = get_wsgi_application()

# Vercel (runtime Python serverless) recherche une variable `app` exposant le
# callable WSGI. Alias de `application`, sans effet en local ni sous un serveur
# WSGI classique.
app = application
