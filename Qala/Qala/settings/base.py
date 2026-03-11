# Qala/settings/base.py
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY  = config('DJANGO_SECRET_KEY', default='local-dev-secret-key-change-in-prod')
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='*', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'core',            # ← auth, users, permissions
    'seller_profile',
    'discovery',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.SuperTokensSessionMiddleware',   # ← core
]

ROOT_URLCONF = 'Qala.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

WSGI_APPLICATION = 'Qala.wsgi.application'

AUTH_USER_MODEL = 'core.User'    # ← core

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N      = True
USE_TZ        = True

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

DATA_UPLOAD_MAX_MEMORY_SIZE = 110 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 110 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'content-type',
    'authorization',
    'x-profile-id',
    'rid',
    'fdi-version',
    'anti-csrf',
    'st-auth-mode',
    'st-refresh-token',
    'st-access-token',
    'front-token',
]
CORS_EXPOSE_HEADERS = ['front-token', 'st-access-token', 'st-refresh-token']

# ── REST FRAMEWORK ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.SuperTokensAuthentication',    # ← core
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'core.utils.custom_exception_handler',   # ← core
}

# ── SUPERTOKENS ───────────────────────────────────────────────────────────────
SUPERTOKENS = {
    'SUPERTOKENS_URL': config('SUPERTOKENS_URL',         default='http://localhost:3567'),
    'API_KEY':         config('SUPERTOKENS_API_KEY',     default='70031101955ba2c956c9f6dd5469fa65a85bc91d'),
    'APP_NAME':        config('SUPERTOKENS_APP_NAME',    default='Qala'),
    'API_DOMAIN':      config('SUPERTOKENS_API_DOMAIN',  default='http://localhost:8000'),
    'WEBSITE_DOMAIN':  config('SUPERTOKENS_WEBSITE_DOMAIN', default='http://localhost:3000'),
}
SUPERTOKENS_HOOK_SECRET = config('SUPERTOKENS_HOOK_SECRET', default='local-hook-secret-dev')