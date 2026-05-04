#!/usr/bin/env bash
# Bulk-seed AWS MySQL after an SSH tunnel maps host port → EC2 MySQL 3306.
# Usage:
#   Terminal 1: ssh -i ./linkedin-sim-key.pem -L 3307:127.0.0.1:3306 ec2-user@<EC2_PUBLIC_IP>
#   Terminal 2: cp .env.aws.mysql.example .env.aws.mysql   # edit if needed
#              set -a && source .env.aws.mysql && set +a && ./scripts/bulk_seed_aws_mysql.sh
#
# Optional: BULK_SEED_RUN_ID=aws1 (default). Override CSV paths with JOBS_CSV / RESUME_CSV.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "${1:-}" && -f "$1" ]]; then
  # shellcheck disable=1090
  set -a && source "$1" && set +a
elif [[ -f .env.aws.mysql ]]; then
  # shellcheck disable=1090
  set -a && source .env.aws.mysql && set +a
fi

: "${MYSQL_HOST:?Set MYSQL_HOST (127.0.0.1 when using ssh -L tunnel)}"
: "${MYSQL_PORT:?Set MYSQL_PORT (e.g. 3307 — see infra/ecs-ec2/README.md)}"
: "${MYSQL_USER:?Set MYSQL_USER}"
: "${MYSQL_PASSWORD:?Set MYSQL_PASSWORD}"
: "${MYSQL_DATABASE:=linkedin_sim}"

RUN_ID="${BULK_SEED_RUN_ID:-aws1}"
JOBS_CSV="${JOBS_CSV:-data/kaggle/job_postings.csv}"
RESUME_CSV="${RESUME_CSV:-data/kaggle_download/Resume/Resume.csv}"
COMPANIES_CSV="${COMPANIES_CSV:-}"
if [[ -z "$COMPANIES_CSV" ]]; then
  _d="$(dirname "$JOBS_CSV")"
  if [[ -f "$_d/companies.csv" ]]; then
    COMPANIES_CSV="$_d/companies.csv"
  fi
fi

if [[ "$MYSQL_HOST" == "mysql" ]]; then
  echo "MYSQL_HOST is 'mysql' (Docker service name). For AWS, use 127.0.0.1 + an SSH tunnel" >&2
  echo "or the private IP if you run this script on the EC2 host. See .env.aws.mysql.example." >&2
  exit 1
fi

echo "Seeding AWS MySQL at ${MYSQL_HOST}:${MYSQL_PORT} database=${MYSQL_DATABASE} run-id=${RUN_ID}"

python3 << PY
import os, subprocess, sys
import pymysql
try:
    pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ["MYSQL_PORT"]),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        connect_timeout=12,
    ).close()
except Exception as e:
    print("MySQL connection failed:", e, file=sys.stderr)
    print("Open an SSH tunnel first, e.g.:", file=sys.stderr)
    print("  ssh -i ./linkedin-sim-key.pem -L 3307:127.0.0.1:3306 ec2-user@<EC2_IP>", file=sys.stderr)
    sys.exit(1)
print("MySQL: connected.")
PY

sub=(python3 scripts/bulk_seed_datasets.py)
_jobs_extra=()
[[ -n "$COMPANIES_CSV" && -f "$COMPANIES_CSV" ]] && _jobs_extra+=(--companies-csv "$COMPANIES_CSV")
"${sub[@]}" jobs --csv "$JOBS_CSV" "${_jobs_extra[@]}" --recruiters 500 --jobs 10000 --run-id "$RUN_ID" --replace-run
"${sub[@]}" members --csv "$RESUME_CSV" --members 1000 --run-id "$RUN_ID" --replace-run
"${sub[@]}" applications --run-id "$RUN_ID" --replace-run

echo "Done. Seeded run-id=${RUN_ID} on ${MYSQL_HOST}:${MYSQL_PORT}."
