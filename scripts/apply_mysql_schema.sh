#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/.env"
  set +a
fi

MYSQL_SERVICE_NAME="${MYSQL_SERVICE_NAME:-mysql}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-${MYSQL_ROOT_PASSWORD:-root}}"
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"

mysql_exec() {
  docker compose exec -T "${MYSQL_SERVICE_NAME}" sh -lc     "mysql --protocol=TCP -h'${MYSQL_HOST}' -P'${MYSQL_PORT}' -u'${MYSQL_USER}' -p'${MYSQL_PASSWORD}'"
}

echo "Waiting for MySQL TCP endpoint ${MYSQL_HOST}:${MYSQL_PORT} inside ${MYSQL_SERVICE_NAME}..."
for attempt in $(seq 1 60); do
  if docker compose exec -T "${MYSQL_SERVICE_NAME}" sh -lc     "mysqladmin --protocol=TCP -h'${MYSQL_HOST}' -P'${MYSQL_PORT}' -u'${MYSQL_USER}' -p'${MYSQL_PASSWORD}' ping --silent" >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    echo "MySQL is not reachable over TCP after waiting." >&2
    docker compose logs --tail=200 "${MYSQL_SERVICE_NAME}" || true
    exit 1
  fi
  sleep 2
done

for file in infra/mysql/*.sql; do
  echo "Applying $file"
  mysql_exec < "$file"
done

echo "MySQL schema applied."
