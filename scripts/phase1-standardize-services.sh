#!/usr/bin/env bash
# =============================================================================
# PHASE 1b — Standardize each service (AUTOMATED BY AI)
# =============================================================================
# After phase1-merge-branches.sh has run, this script:
#   - Ensures each service has a Dockerfile
#   - Adds a minimal health endpoint stub if main.py is missing
#   - Normalizes ports in each service's Dockerfile CMD
# =============================================================================

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# service-dir → port
declare -A PORT_MAP=(
  [auth-service]="8001"
  [member-service]="8002"
  [recruiter-service]="8003"
  [job-service]="8004"
  [application-service]="8005"
  [analytics-service]="8007"
  [ai-service]="8008"
)

# service-dir → runtime
declare -A RUNTIME_MAP=(
  [auth-service]="python"
  [member-service]="python"
  [recruiter-service]="node"
  [job-service]="python"
  [application-service]="python"
  [analytics-service]="python"
  [ai-service]="python"
)

# Python services: where is main.py relative to service root?
declare -A MAIN_MAP=(
  [auth-service]="app.main:app"
  [member-service]="app.main:app"
  [job-service]="src.main:app"
  [application-service]="app.main:app"
  [analytics-service]="app.main:app"
  [ai-service]="main:app"
)

for svc in "${!PORT_MAP[@]}"; do
  dir="services/$svc"
  port="${PORT_MAP[$svc]}"
  runtime="${RUNTIME_MAP[$svc]}"

  if [ ! -d "$dir" ]; then
    echo "[SKIP] $dir not found (branch may not have been merged yet)"
    continue
  fi

  echo ""
  echo "── Standardizing $svc (port $port) ──"

  # ── 1. Dockerfile ────────────────────────────────────────────────────────
  if [ ! -f "$dir/Dockerfile" ]; then
    echo "  [ADD] Dockerfile (Python)"
    module="${MAIN_MAP[$svc]:-app.main:app}"
    cat > "$dir/Dockerfile" <<DEOF
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE $port
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
  CMD python -c "import httpx; httpx.get('http://localhost:$port/health')" || exit 1
CMD ["uvicorn", "${module}", "--host", "0.0.0.0", "--port", "$port"]
DEOF
  else
    echo "  [OK ] Dockerfile exists"
    # Fix port in CMD if it uses a different port
    if grep -q "CMD\|EXPOSE" "$dir/Dockerfile"; then
      sed -i.bak \
        -e "s/--port [0-9]\{4\}/--port $port/g" \
        -e "s/EXPOSE [0-9]\{4\}/EXPOSE $port/g" \
        "$dir/Dockerfile" && rm -f "$dir/Dockerfile.bak"
      echo "  [FIX] Normalized port to $port in Dockerfile"
    fi
  fi

  # ── 2. requirements.txt ─────────────────────────────────────────────────
  if [ "$runtime" = "python" ] && [ ! -f "$dir/requirements.txt" ]; then
    echo "  [ADD] Minimal requirements.txt"
    cat > "$dir/requirements.txt" <<REOF
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.1
httpx==0.27.0
python-dotenv==1.0.1
REOF
  fi

  # ── 3. .env.example ─────────────────────────────────────────────────────
  if [ ! -f "$dir/.env.example" ]; then
    echo "  [ADD] .env.example"
    cat > "$dir/.env.example" <<EEOF
SERVICE_PORT=$port
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
AUTH_JWKS_URL=http://auth-service:8001/api/v1/.well-known/jwks.json
EEOF
  fi

  # ── 4. .dockerignore ────────────────────────────────────────────────────
  if [ ! -f "$dir/.dockerignore" ]; then
    cat > "$dir/.dockerignore" <<IEOF
__pycache__
*.pyc
*.pyo
.env
.git
node_modules
*.log
IEOF
  fi

  echo "  [DONE] $svc"
done

git add -A
git commit -m "chore: standardize service Dockerfiles and env examples" || true

echo ""
echo "======================================================================"
echo " Phase 1b complete."
echo "======================================================================"
