#!/bin/sh
set -eu

if [ -z "${POSTGRES_APP_USER:-}" ] || [ -z "${POSTGRES_APP_PASSWORD:-}" ]; then
    echo "POSTGRES_APP_USER and POSTGRES_APP_PASSWORD are required" >&2
    exit 1
fi

psql --set=ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set=app_user="$POSTGRES_APP_USER" \
    --set=app_password="$POSTGRES_APP_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE bsrm_booking_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bsrm_booking_app')
\gexec

SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS',
    :'app_user',
    :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')
\gexec

SELECT format('GRANT bsrm_booking_app TO %I', :'app_user')
\gexec
SQL
