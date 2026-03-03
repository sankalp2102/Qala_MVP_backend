# Qala/settings/local.py
from .base import *

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME':   BASE_DIR / 'db.sqlite3',
    }
}

CORS_ALLOW_ALL_ORIGINS = True

SUPERTOKENS = {
    'SUPERTOKENS_URL':     'http://34.169.72.66:3567',
    'API_KEY':             '70031101955ba2c956c9f6dd5469fa65a85bc91d',
    'APP_NAME':            'Qala',
    'API_DOMAIN':          'http://localhost:8000',
    'WEBSITE_DOMAIN':      'http://localhost:3000',
}
SUPERTOKENS_HOOK_SECRET = 'local-hook-secret-dev'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO'},
        'core':   {'handlers': ['console'], 'level': 'DEBUG'},   # ← core
    },
}