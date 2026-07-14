import os
import sys
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "clave-insegura-solo-para-desarrollo")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# --- Bootstrap de microservicio (no proviene del Config Server, evita circularidad) ---
NOMBRE_SERVICIO = os.environ.get("NOMBRE_SERVICIO", "servicio-pedidos")
DJANGO_PERFIL = os.environ.get("DJANGO_PERFIL", "docker")
REGISTRO_SERVICIOS_URL = os.environ.get("REGISTRO_SERVICIOS_URL", "http://registro-servicios:8500")
CONFIG_SERVER_URL = os.environ.get("CONFIG_SERVER_URL", "http://config-server:8600")
SERVICIO_HOST = os.environ.get("SERVICIO_HOST", NOMBRE_SERVICIO)
SERVICIO_PUERTO = int(os.environ.get("SERVICIO_PUERTO", "8004"))

INSTALLED_APPS = [
    # auth/contenttypes se incluyen solo porque rest_framework_simplejwt.tokens los
    # importa a nivel de modulo (AbstractBaseUser); este servicio NO tiene tabla de
    # usuarios propia ni usa AUTH_USER_MODEL, la autenticacion es stateless (core.auth).
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "corsheaders",
    "pedidos",
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
# dev (docker-compose) y prod: SQL Server dedicado via mssql-django/pyodbc
DB_HOST = os.environ.get("DB_HOST")
if DB_HOST:
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.environ.get("DB_NAME", "pedidos_db"),
            "USER": os.environ.get("DB_USER", "sa"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": DB_HOST,
            "PORT": os.environ.get("DB_PORT", "1433"),
            "OPTIONS": {
                "driver": "ODBC Driver 18 for SQL Server",
                "extra_params": "TrustServerCertificate=yes",
            },
            "CONN_MAX_AGE": 600,
        }
    }
else:
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

# HU14 - comision fija de plataforma que corresponde al repartidor por cada pago
REPARTIDOR_COMISION_PORCENTAJE = Decimal(os.environ.get("REPARTIDOR_COMISION_PORCENTAJE", "10.00"))

if "test" in sys.argv:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
