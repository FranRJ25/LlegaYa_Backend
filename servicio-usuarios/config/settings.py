import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "clave-insegura-solo-para-desarrollo")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# --- Bootstrap de microservicio (no proviene del Config Server, evita circularidad) ---
NOMBRE_SERVICIO = os.environ.get("NOMBRE_SERVICIO", "servicio-usuarios")
DJANGO_PERFIL = os.environ.get("DJANGO_PERFIL", "docker")
REGISTRO_SERVICIOS_URL = os.environ.get("REGISTRO_SERVICIOS_URL", "http://registro-servicios:8500")
CONFIG_SERVER_URL = os.environ.get("CONFIG_SERVER_URL", "http://config-server:8600")
SERVICIO_HOST = os.environ.get("SERVICIO_HOST", NOMBRE_SERVICIO)
SERVICIO_PUERTO = int(os.environ.get("SERVICIO_PUERTO", "8001"))

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "usuarios",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Base de datos ---
# dev (docker-compose): Postgres compartido -> DATABASE_URL=postgres://.../usuarios_db
# prod (k8s): SQLite persistido en PVC
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "data" / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "usuarios.Usuario"

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS ---
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:4200,http://localhost:8080"
    ).split(",") if o
]
FRONTEND_URL_PROD = os.environ.get("FRONTEND_URL_PROD")
if FRONTEND_URL_PROD:
    CORS_ALLOWED_ORIGINS.append(FRONTEND_URL_PROD)

# --- Email (reset de contraseña) ---
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = f"LlegaYa <{EMAIL_HOST_USER}>"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:4200")

# Tests: sqlite en memoria
if "test" in sys.argv:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
