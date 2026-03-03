"""
WSGI config for Qala project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

# Qala/wsgi.py
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Qala.settings.production')

# SuperTokens routing is handled by core.middleware.SuperTokensSessionMiddleware
# in MIDDLEWARE list in settings/base.py — no wrapping needed here.
application = get_wsgi_application()
