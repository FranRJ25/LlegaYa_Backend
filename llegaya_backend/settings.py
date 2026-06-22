"""
Django settings for llegaya_backend project.
"""

from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()
import os
import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent


# ── Seguridad ──────────────────────────────────────────
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-w$u4w&@98)d^n$(aq#y6nvx0nu7f#f=+cw+1t-$mh!vbo(as*h'
)

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [
    'llegaya-backend.onrender.com',
    'localhost',
    '127.0.0.1',
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'rest_framework_simplejwt.token_blacklist',
    'apps.security',
]

AUTH_USER_MODEL = 'security.Usuario'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'llegaya_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'llegaya_backend.wsgi.application'


# ── Base de datos ────────────────────────────────────────
# En Render usamos DATABASE_URL (variable de entorno).
# En local, si no existe DATABASE_URL, usa los datos de Supabase directos.

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     'postgres',
            'USER':     'postgres.rxfvcfmtdtqxswpgoqdp',
            'PASSWORD': 'llegaya123.',
            'HOST':     'aws-1-us-west-2.pooler.supabase.com',
            'PORT':     '6543',
        }
    }


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ── Static files (necesario para Whitenoise/Render) ──────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'                                  # ← agregado
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'  # ← agregado


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  True,

    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ── CORS ──────────────────────────────────────────────────
CORS_ALLOW_CREDENTIALS = True   # necesario para que el browser envíe/reciba cookies cross-origin

CORS_ALLOW_HEADERS = [          # explícito para que el frontend pueda enviar Authorization + Content-Type
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "https://llega-ya-fronted-eosin.vercel.app",
    "https://llegaya-backend.onrender.com"
]
# Agrega aquí la URL real de tu frontend cuando la tengas, ej:
# CORS_ALLOWED_ORIGINS.append("https://llegaya-frontend.onrender.com")

frontend_extra = os.environ.get('FRONTEND_URL_PROD')
if frontend_extra:
    CORS_ALLOWED_ORIGINS.append(frontend_extra)


MEDIA_URL  = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = f'LlegaYa <{os.environ.get("EMAIL_HOST_USER", "")}>'

# URL del frontend para construir links (reset password, etc.)
# En local usa localhost, en Render usa la variable de entorno.
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:4200')
