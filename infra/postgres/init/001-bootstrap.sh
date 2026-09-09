#!/usr/bin/env sh
set -eu

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${AUTH_DB_PASSWORD:?AUTH_DB_PASSWORD is required}"
: "${EVENT_DB_PASSWORD:?EVENT_DB_PASSWORD is required}"
: "${MEDIA_DB_PASSWORD:?MEDIA_DB_PASSWORD is required}"
: "${ANALYTICS_DB_PASSWORD:?ANALYTICS_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v auth_db_password="$AUTH_DB_PASSWORD" \
  -v event_db_password="$EVENT_DB_PASSWORD" \
  -v media_db_password="$MEDIA_DB_PASSWORD" \
  -v analytics_db_password="$ANALYTICS_DB_PASSWORD" <<'SQL'
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS events;
CREATE SCHEMA IF NOT EXISTS media;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE ROLE pawprints_auth_rw LOGIN PASSWORD :'auth_db_password';
CREATE ROLE pawprints_event_rw LOGIN PASSWORD :'event_db_password';
CREATE ROLE pawprints_media_rw LOGIN PASSWORD :'media_db_password';
CREATE ROLE pawprints_analytics_ro LOGIN PASSWORD :'analytics_db_password';

GRANT USAGE, CREATE ON SCHEMA auth TO pawprints_auth_rw;
GRANT USAGE, CREATE ON SCHEMA events TO pawprints_event_rw;
GRANT USAGE, CREATE ON SCHEMA media TO pawprints_media_rw;
GRANT USAGE ON SCHEMA events TO pawprints_analytics_ro;
SQL
