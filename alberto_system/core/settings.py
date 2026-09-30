"""
Django Settings for Alberto Grocers Inventory POS.

This file contains all configuration for the Django project, including
database connections, installed applications, security headers, and 
third-party integrations (DRF, Simple History, Crispy Forms).

Environment variables are strictly managed using python-decouple to 
ensure safe deployments to platforms like Render.
"""

import os
from pathlib import Path
from decimal import Decimal

import dj_database_url
from decouple import Csv, config

# ==============================================================================
# 1. BASE CONFIGURATION
# ==============================================================================
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security Warning: Keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-this-in-prod')

# Auto-Detect Environment:
# This system is LOCAL-ONLY (one shop, one PC, no online deployment), so DEBUG
# defaults to True. That default is deliberate: with the old default of False, a
# lost or unreadable .env silently enabled the production hardening block further
# down (SECURE_SSL_REDIRECT, secure cookies). Every plain-HTTP request to
# http://127.0.0.1:8000 would then be redirected to HTTPS and the whole app would
# look broken with no obvious cause. Keep DEBUG True.
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost,web', cast=Csv())

# Fix for Render's Health Check and Custom Domains (Only applies if DEBUG is False)
if not DEBUG:
    CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']


# ==============================================================================
# 2. APPLICATION DEFINITION
# ==============================================================================
INSTALLED_APPS =[
    # Core Django Apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Local Apps
    'inventory',

    # Third-Party Apps
    'rest_framework',
    'rest_framework.authtoken',
    'simple_history',
    'drf_spectacular',
    'crispy_forms',
    'crispy_bootstrap5',
    'cloudinary',
    'cloudinary_storage',
]

MIDDLEWARE =[
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serves static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'core.middleware.NoCacheMiddleware',
]

ROOT_URLCONF = 'core.urls'

# ==============================================================================
# 3b. TEMPLATE CACHE  (read this before assuming "the server ignored my edit")
# ==============================================================================
# Django >= 2.0 ALWAYS wraps the template loaders in cached.Loader, even when
# DEBUG=True (see django/template/engine.py: loaders are wrapped unconditionally
# unless 'loaders' is given explicitly). A cached template is compiled once and
# held in memory for the lifetime of the process, so an already-running
# `--noreload` dev server keeps serving the OLD template until it restarts.
#
# That combination (`--noreload` + cached.Loader) is the single most confusing
# failure in this project: you edit a .html file, refresh, and see the old page,
# so you restart the server "to be safe" over and over.
#
# scripts/server.ps1 therefore starts the DEV server with TEMPLATE_CACHE=false,
# which opts out of the cache and makes template edits appear on the next
# refresh. Production leaves it unset (true) and keeps the faster cached path.
TEMPLATE_CACHE = config('TEMPLATE_CACHE', default=True, cast=bool)

_TEMPLATE_OPTIONS = {
    'context_processors':[
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'core.context_processors.notifications',
    ],
}

if not TEMPLATE_CACHE:
    # Naming 'loaders' explicitly is the ONLY way to bypass cached.Loader.
    # Django raises ImproperlyConfigured if 'loaders' and APP_DIRS are both set,
    # hence APP_DIRS is driven by the same flag below.
    _TEMPLATE_OPTIONS['loaders'] = [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]

TEMPLATES =[
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': TEMPLATE_CACHE,
        'OPTIONS': _TEMPLATE_OPTIONS,
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# ==============================================================================
# 3. DATABASE CONFIGURATION
# ==============================================================================
# Logic: 
# - Uses Render PostgreSQL if DATABASE_URL is set in environment.
# - Falls back to local SQLite for local development.
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'),
        conn_max_age=600
    )
}


# ==============================================================================
# 4. PASSWORD VALIDATION
# ==============================================================================
AUTH_PASSWORD_VALIDATORS =[
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ==============================================================================
# 5. INTERNATIONALIZATION
# ==============================================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True


# ==============================================================================
# 6. STATIC & MEDIA FILES
# ==============================================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Ensures WhiteNoise handles files even when DEBUG is True (fixes Windows/Docker issues)
WHITENOISE_USE_FINDERS = True
# NOTE: the old `STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'`
# line was removed. Django 5.1 DELETED the STATICFILES_STORAGE/DEFAULT_FILE_STORAGE
# transitional settings, so that assignment was inert - it never took effect. The honoured
# equivalent now lives in STORAGES below.

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# 6b. FILE STORAGE (Cloudinary) - receipts must not die with the container
# ==============================================================================
# BUG THIS FIXES: Django 5.1 removed DEFAULT_FILE_STORAGE, so the old
# `DEFAULT_FILE_STORAGE = 'cloudinary_storage...'` line did nothing. Every
# Expense.receipt upload silently fell back to FileSystemStorage, i.e. MEDIA_ROOT
# on the server's own disk. On Render that disk is EPHEMERAL, so uploaded receipts
# were lost on every deploy or restart. STORAGES is the only mechanism Django 5.x
# honours.
#
# ZERO-REGRESSION RULE: Cloudinary is used ONLY when a cloud name is actually
# configured. A key that is present but EMPTY (which is the case in the local
# .env, and in Render where no CLOUDINARY_* vars are set) counts as "not
# configured", so the backend stays FileSystemStorage - byte-identical to today's
# behaviour. Add real CLOUDINARY_* values to Render's dashboard and uploads move
# to Cloudinary automatically, with no further code change.
CLOUDINARY_CLOUD_NAME = config('CLOUDINARY_CLOUD_NAME', default='')
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
    'API_KEY': config('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': config('CLOUDINARY_API_SECRET', default=''),
}
USE_CLOUDINARY = bool(CLOUDINARY_CLOUD_NAME.strip())

STORAGES = {
    'default': {
        'BACKEND': (
            'cloudinary_storage.storage.MediaCloudinaryStorage'
            if USE_CLOUDINARY
            else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    # Deliberately Django's default rather than the hashed manifest variant: a
    # single file missing from staticfiles/ becomes a hard collectstatic error at
    # deploy time, which is a worse trade than losing long-cache static headers.
    # WhiteNoise already serves whatever collectstatic produced.
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


# ==============================================================================
# 7. SESSION MANAGEMENT & SECURITY
# ==============================================================================
# Default expiry is 2 weeks (1,209,600 seconds)
SESSION_COOKIE_AGE = 1209600 

# Attempt to expire session when browser closes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# CRITICAL: Reset session timer on every request to keep active users logged in
SESSION_SAVE_EVERY_REQUEST = True

# Production Security Flags
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True


# ==============================================================================
# 8. AUTHENTICATION ROUTING
# ==============================================================================
# Cashiers land straight on the POS terminal after signing in; the dashboard is
# still reachable at /dashboard/ and from the terminal's burger menu.
LOGIN_REDIRECT_URL = '/inventory/pos/'
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/accounts/login/'


# ==============================================================================
# 8b. POINT OF SALE TERMINAL
# ==============================================================================
# Philippine retail VAT. Shelf prices are treated as VAT-INCLUSIVE, so the
# terminal extracts the tax out of the total for display:
#   subtotal = total / (1 + POS_TAX_RATE/100)
#   tax      = total - subtotal
# Each POSSale stores the rate actually applied, so historic receipts keep
# showing the rate in force when they were rung up.
POS_TAX_RATE = Decimal('15.00')


# ==============================================================================
# 9. THIRD-PARTY APP CONFIGURATIONS
# ==============================================================================

# Django REST Framework & Swagger (drf-spectacular)
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES':[
        'rest_framework.authentication.TokenAuthentication',
    ],
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Alberto Grocers Inventory API',
    'DESCRIPTION': 'A comprehensive API for Alberto Grocers managing products, stock, and transactions.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SORT_TAGS_BY_NAME': True,
}

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"