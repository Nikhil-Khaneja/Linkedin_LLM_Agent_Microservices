#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

cp -n .env.example .env || true
set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source .env
set +a
python3 scripts/reset_dev_state.py || true

SERVICES_INFRA=(mysql mongo redis kafka minio prometheus grafana)
SERVICES_APP=(auth_service member_profile_service recruiter_company_service jobs_service applications_service messaging_connections_service analytics_service ai_orchestrator_service frontend)

echo '[1/7] Starting infrastructure and observability'
docker compose up -d mysql mongo redis kafka minio loki promtail prometheus grafana

echo '[2/7] Waiting for infrastructure'
python3 scripts/wait_for_stack.py "${SERVICES_INFRA[@]}"

echo '[3/7] Applying MySQL schema and indexes'
./scripts/apply_mysql_schema.sh

echo '[4/7] Applying Mongo collections and indexes'
./scripts/apply_mongo_init.sh

echo '[5/7] Ensuring Kafka topics exist'
./scripts/create_kafka_topics.sh

echo '[6/7] Starting backend services and frontend'
docker compose up --build -d auth_service member_profile_service recruiter_company_service jobs_service applications_service messaging_connections_service analytics_service ai_orchestrator_service frontend
python3 scripts/wait_for_stack.py "${SERVICES_APP[@]}"

echo '[7/7] Seeding demo data'
python3 scripts/seed_demo_data.py || true

echo 'Stack ready'
echo 'Frontend:   http://localhost:5173'
echo "Grafana:    http://localhost:${GRAFANA_PUBLISH_PORT:-3000}  (admin/admin)"
echo 'Prometheus: http://localhost:9090'
echo 'Owner 1:    http://localhost:8001/docs'
echo 'Owner 6:    http://localhost:8006/docs'
echo 'Owner 7:    http://localhost:8007/docs'
echo 'Owner 8:    http://localhost:8008/docs'
