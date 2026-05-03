#!/usr/bin/env bash
# Bring the stack up, wait for health, sync bulk-import login in Docker MySQL, seed demo data.
# Then open: http://localhost:5173
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source .env
set +a

echo "[1/5] docker compose up -d"
docker compose up -d

echo "[2/5] Kafka topics (slow on cold cache; safe to re-run)"
bash scripts/create_kafka_topics.sh

echo "[3/5] Wait for core services + frontend"
WAIT_FOR_STACK_TIMEOUT="${WAIT_FOR_STACK_TIMEOUT:-600}" python3 scripts/wait_for_stack.py \
  mysql mongo redis kafka minio \
  auth_service member_profile_service recruiter_company_service jobs_service applications_service \
  messaging_connections_service analytics_service ai_orchestrator_service frontend

echo "[4/5] Bulk recruiter password in container MySQL (matches auth SHA256)"
HASH="$(python3 -c "import hashlib; print(hashlib.sha256('KaggleImport#2026'.encode()).hexdigest())")"
docker compose exec -T mysql sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" linkedin_sim -e \"UPDATE users SET email='bulk-kaggle-recruiter@example.com', password_hash='${HASH}' WHERE user_id='rec_kaggle_import'; UPDATE recruiters SET email='bulk-kaggle-recruiter@example.com' WHERE recruiter_id='rec_kaggle_import';\""

echo "[5/5] Demo seed (HTTP; ok if partially already seeded)"
python3 scripts/seed_demo_data.py || true

# Optional: small synthetic bulk jobs for the Kaggle-import recruiter (fast UI checks; not the full dataset).
# From the host, talk to MySQL on the published port, not the docker hostname "mysql".
if [[ "${LOAD_LIGHT_SYNTHETIC_JOBS:-}" == "1" ]]; then
  echo "[optional] Light synthetic jobs (LOAD_LIGHT_SYNTHETIC_JOBS=1)"
  MYSQL_HOST=127.0.0.1 MYSQL_PORT="${MYSQL_PUBLISH_PORT:-3306}" \
    python3 scripts/load_kaggle_datasets.py --synthetic --max-jobs 400 --max-members 80 --chunk-size 200 || true
fi

echo ""
echo "Fast job keyword search (fulltext index):  bash scripts/apply_mysql_schema.sh"
echo "Ready. Open:  http://localhost:5173"
echo "Optional bulk sample (host MySQL):  LOAD_LIGHT_SYNTHETIC_JOBS=1 bash scripts/prep_for_browser_test.sh"
echo "Bulk import recruiter (Kaggle / synthetic under that account):  bulk-kaggle-recruiter@example.com  /  KaggleImport#2026"
echo "Demo recruiter (seed):  recruiter@example.com  (password from seed_demo_data / register flow)"
echo "Grafana:  http://localhost:${GRAFANA_PUBLISH_PORT:-3000}  (admin/admin)"
