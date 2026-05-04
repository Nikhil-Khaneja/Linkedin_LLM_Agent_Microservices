#!/usr/bin/env bash
# Run bulk MySQL seed ON the EC2 instance (no laptop SSH tunnel to MySQL).
# Requires: repo (or synced CSVs) on the box, Python 3 + pymysql, Docker platform task running MySQL.
#
#   ssh ec2-user@<EC2_IP>
#   cd ~/Linkedin_Prototype_LLM_Agent_Microservices   # or your clone path
#   pip3 install --user pymysql   # if needed
#   ./scripts/bulk_seed_on_ec2_host.sh
#
# Optional: BULK_SEED_RUN_ID=aws1 JOBS_CSV=... RESUME_CSV=...

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# This script talks to MySQL via Docker on the *instance*. On a Mac/Windows dev machine use
# ./scripts/populate_aws_mysql.sh or an SSH tunnel + ./scripts/bulk_seed_aws_mysql.sh instead.
case "$(uname -s)" in
  Darwin|MINGW*|MSYS_NT*)
    echo "bulk_seed_on_ec2_host.sh is for the EC2 Linux host only (it uses docker to find MySQL)." >&2
    echo "" >&2
    echo "From your laptop → AWS MySQL, run:" >&2
    echo "  ./scripts/populate_aws_mysql.sh" >&2
    echo "or open a tunnel then ./scripts/bulk_seed_aws_mysql.sh (see data/README.md)." >&2
    exit 1
    ;;
esac

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

export MYSQL_USER="${MYSQL_USER:-root}"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-root}"
export MYSQL_DATABASE="${MYSQL_DATABASE:-linkedin_sim}"
export MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"

if [[ -z "${MYSQL_PORT:-}" ]]; then
  MYSQL_PORT="$(python3 << 'PY'
import re, subprocess
for cmd in (["docker", "ps", "--format", "{{.Ports}}"], ["sudo", "docker", "ps", "--format", "{{.Ports}}"]):
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=15)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        continue
    for line in out.splitlines():
        for pat in (r"0\.0\.0\.0:(\d+)->3306/tcp", r":::(\d+)->3306/tcp", r"0\.0\.0\.0:(\d+)->3306"):
            m = re.search(pat, line)
            if m:
                print(m.group(1))
                raise SystemExit
print("3306")
PY
)"
fi
export MYSQL_PORT

echo "Using MySQL ${MYSQL_HOST}:${MYSQL_PORT} (run-id=${RUN_ID})"
python3 - << PY
import os, sys
try:
    import pymysql
    pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ["MYSQL_PORT"]),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        connect_timeout=10,
    ).close()
except Exception as e:
    print("MySQL check failed:", e, file=sys.stderr)
    print("On EC2: ensure the linkedin-sim-platform task is running (docker ps shows mysql).", file=sys.stderr)
    print("If MySQL is not on 3306 from the host, set MYSQL_PORT to the mapped port from: docker ps", file=sys.stderr)
    sys.exit(1)
print("MySQL: ok")
PY

py=(python3 scripts/bulk_seed_datasets.py)
"${py[@]}" jobs --csv "$JOBS_CSV" --recruiters 500 --jobs 10000 --run-id "$RUN_ID" --replace-run \
  ${COMPANIES_CSV:+--companies-csv "$COMPANIES_CSV"}
"${py[@]}" members --csv "$RESUME_CSV" --members 1000 --run-id "$RUN_ID" --replace-run
"${py[@]}" applications --run-id "$RUN_ID" --replace-run

echo "Done (EC2 host seed, run-id=${RUN_ID})."
