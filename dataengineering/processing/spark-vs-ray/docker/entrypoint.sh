#!/usr/bin/env bash
set -euo pipefail

export AIRFLOW_HOME="${AIRFLOW_HOME:-/opt/airflow}"

mkdir -p "$AIRFLOW_HOME"

# Initialize DB (sqlite) and create an admin user with simple credentials for the tutorial.
airflow db migrate

airflow users create \
  --username "${AIRFLOW_ADMIN_USER:-admin}" \
  --password "${AIRFLOW_ADMIN_PASS:-admin}" \
  --firstname "Admin" \
  --lastname "User" \
  --role "Admin" \
  --email "admin@example.com" || true

# Start scheduler in background, webserver in foreground.
airflow scheduler &
exec airflow webserver



