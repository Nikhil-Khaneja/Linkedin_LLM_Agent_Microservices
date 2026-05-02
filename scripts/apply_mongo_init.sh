#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T mongo mongosh --quiet /docker-entrypoint-initdb.d/init.js

echo "Mongo init applied."
