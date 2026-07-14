import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "clave-insegura-solo-para-desarrollo")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# --- Bootstrap de microservicio (no proviene del Config Server, evita circularidad) ---
NOMBRE_SERVICIO = os.environ.get("NOMBRE_SERVICIO", "servicio-repartidores")
DJANGO_PERFIL = os.environ.get("DJANGO_PERFIL", "docker")
REGISTRO_SERVICIOS_URL = os.environ.get("REGISTRO_SERVICIOS_URL", "http://registro-servicios:8500")
CONFIG_SERVER_URL = os.environ.get("CONFIG_SERVER_URL", "http://config-server:8600")
SERVICIO_HOST = os.environ.get("SERVICIO_HOST", NOMBRE_SERVICIO)
SERVICIO_PUERTO = int(os.environ.get("SERVICIO_PUERTO", "8005"))

# --- MongoDB (dominio: PerfilRepartidor via mongoengine) ---
# dev (docker-compose): contenedor mongo. prod (k8s): MongoDB externo (ej. Atlas) vía Secret.
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/repartidores_db")

INSTALLED_APPS = [
    # auth/contenttypes se incluyen solo porque rest_framework_simplejwt.tokens los
    # importa a nivel de modulo (AbstractBaseUser); este servicio NO tiene tabla de
    # usuarios propia ni usa AUTH_USER_MODEL, la autenticacion es stateless (core.auth).
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "corsheaders",
    "repartidores",
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

# Django exige un DATABASES['default'] aunque no se use para datos de dominio
# (los datos de PerfilRepartidor viven en Mongo). Solo sirve para auth/contenttypes.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "db.sqlite3",
    }
}

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("core.auth.StatelessJWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

SIMPLE_JWT = {
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
}

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:4200,http://localhost:8080"
    ).split(",") if o
]

# API Gateway (unico punto de entrada para llamadas entre microservicios)
API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL", "http://api-gateway:8080")
ZONA_MIN_PALABRA_LARGO = int(os.environ.get("ZONA_MIN_PALABRA_LARGO", "3"))

USA_MONGOMOCK = "test" in sys.argv
if USA_MONGOMOCK:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    MONGO_URI = "mongodb://localhost/repartidores_test"
