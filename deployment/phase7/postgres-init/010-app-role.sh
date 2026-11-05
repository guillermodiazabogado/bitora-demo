#!/bin/sh
set -eu

test -n "${BITORA_APP_DB_PASSWORD:-}"
psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$BITORA_APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE bitora_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bitora_app')\gexec
SELECT format('ALTER DATABASE %I OWNER TO bitora_app', current_database())\gexec
ALTER SCHEMA public OWNER TO bitora_app;
SELECT format('GRANT CONNECT ON DATABASE %I TO bitora_app', current_database())\gexec
GRANT USAGE, CREATE ON SCHEMA public TO bitora_app;
SQL
