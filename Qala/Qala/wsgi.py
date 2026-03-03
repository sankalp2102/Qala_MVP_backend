"""
WSGI config for Qala project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

# Qala/wsgi.py
import os
from django.core.wsgi import get_wsgi_application
from supertokens_python.framework.django.django_middleware import Middleware

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Qala.settings.production')
application = Middleware(get_wsgi_application())
