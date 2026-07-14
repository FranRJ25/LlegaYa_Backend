#!/bin/sh
set -e

python manage.py migrate --noinput

exec gunicorn config.wsgi:application --bind 0.0.0.0:${SERVICIO_PUERTO:-8001} --workers 1
