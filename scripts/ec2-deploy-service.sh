#!/usr/bin/env bash
# =============================================================================
# PHASE 4 — EC2 Service Deployment Script (AUTOMATED BY AI)
# =============================================================================
# Run this ON the EC2 instance to deploy ONE microservice via Docker.
#
# Usage (SSH into EC2 and run):
#   export SERVICE=auth-service
#   export REPO_URL=https://github.com/YOUR_ORG/linkedin-monorepo.git
#   export SERVICE_PORT=8001
#   bash ec2-deploy-service.sh
#
# Or pass everything inline:
#   SERVICE=job-service SERVICE_PORT=8004 REPO_URL=https://... bash ec2-deploy-service.sh
# =============================================================================

set -euo pipefail

SERVICE="${SERVICE:?Set SERVICE env var, e.g. auth-service}"
SERVICE_PORT="${SERVICE_PORT:?Set SERVICE_PORT env var, e.g. 8001}"
REPO_URL="${REPO_URL:?Set REPO_URL to your git repo}"
BRANCH="${BRANCH:-main}"
APP_DIR="/opt/linkedin/$SERVICE"

echo "======================================================================"
echo " Deploying $SERVICE on port $SERVICE_PORT"
echo "======================================================================"

# ── 1. System packages ───────────────────────────────────────────────────────
if command -v apt-get &>/dev/null; then
  apt-get update -y
  apt-get install -y git docker.io curl
  systemctl enable --now docker
elif command -v yum &>/dev/null; then
  yum update -y
  yum install -y git docker curl
  systemctl enable --now docker
fi

# Allow running docker without sudo
usermod -aG docker "$USER" 2>/dev/null || true

# ── 2. Clone / update repo ───────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
  echo "[UPDATE] Pulling latest $BRANCH"
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  echo "[CLONE] $REPO_URL → $APP_DIR"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

# ── 3. Build Docker image ────────────────────────────────────────────────────
echo "[BUILD] docker build services/$SERVICE"
docker build \
  -t "linkedin-$SERVICE:latest" \
  "$APP_DIR/services/$SERVICE"

# ── 4. Stop existing container if running ───────────────────────────────────
docker stop "linkedin-$SERVICE" 2>/dev/null || true
docker rm   "linkedin-$SERVICE" 2>/dev/null || true

# ── 5. Load .env if it exists ────────────────────────────────────────────────
ENV_FILE="$APP_DIR/services/$SERVICE/.env"
ENV_FLAG=""
if [ -f "$ENV_FILE" ]; then
  ENV_FLAG="--env-file $ENV_FILE"
fi

# ── 6. Run container ─────────────────────────────────────────────────────────
echo "[RUN] Starting linkedin-$SERVICE on :$SERVICE_PORT"
# shellcheck disable=SC2086
docker run -d \
  --name "linkedin-$SERVICE" \
  --restart unless-stopped \
  -p "${SERVICE_PORT}:${SERVICE_PORT}" \
  $ENV_FLAG \
  "linkedin-$SERVICE:latest"

echo ""
echo "[HEALTH] Waiting for service..."
sleep 5
curl -sf "http://localhost:${SERVICE_PORT}/health" && echo " — OK" || echo " — (health check failed, check logs)"

echo ""
echo "======================================================================"
echo " Done. Container: linkedin-$SERVICE  Port: $SERVICE_PORT"
echo " Logs: docker logs -f linkedin-$SERVICE"
echo "======================================================================"
