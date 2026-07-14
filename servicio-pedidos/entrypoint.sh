#!/bin/sh
set -e

if [ -n "$DB_HOST" ]; then
  python - <<'EOF'
import os
import pyodbc

server = f"{os.environ['DB_HOST']},{os.environ.get('DB_PORT', '1433')}"
conn = pyodbc.connect(
    f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
    f"UID={os.environ.get('DB_USER', 'sa')};PWD={os.environ['DB_PASSWORD']};"
    "DATABASE=master;TrustServerCertificate=yes",
    autocommit=True,
)
db_name = os.environ.get("DB_NAME", "pedidos_db")
cursor = conn.cursor()
cursor.execute(
    f"IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = '{db_name}') "
    f"CREATE DATABASE [{db_name}]"
)
conn.close()
EOF
fi

python manage.py migrate --noinput

exec gunicorn config.wsgi:application --bind 0.0.0.0:${SERVICIO_PUERTO:-8004} --workers 1
