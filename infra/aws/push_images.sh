#!/usr/bin/env bash
# Build Docker images and push to ECR
# Usage: ./push_images.sh [--region us-east-1]
set -euo pipefail

REGION=${AWS_DEFAULT_REGION:-us-east-1}
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

BACKEND_REPO="$ECR_BASE/linkedin-sim/backend"
FRONTEND_REPO="$ECR_BASE/linkedin-sim/frontend"
ALB_DNS=$(terraform output -raw alb_dns_name 2>/dev/null || echo "")

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "==> Logging in to ECR…"
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_BASE"

# ── Backend image ─────────────────────────────────────────────────────────────
echo "==> Building backend image…"
docker build -t "$BACKEND_REPO:latest" "$PROJECT_ROOT/backend"
echo "==> Pushing backend image…"
docker push "$BACKEND_REPO:latest"

# ── Frontend image (baked with ALB URLs) ─────────────────────────────────────
echo "==> Building frontend image (ALB=$ALB_DNS)…"
docker build \
  --build-arg "REACT_APP_AUTH_URL=http://$ALB_DNS:8001" \
  --build-arg "REACT_APP_MEMBER_URL=http://$ALB_DNS:8002" \
  --build-arg "REACT_APP_RECRUITER_URL=http://$ALB_DNS:8003" \
  --build-arg "REACT_APP_JOB_URL=http://$ALB_DNS:8004" \
  --build-arg "REACT_APP_APP_URL=http://$ALB_DNS:8005" \
  --build-arg "REACT_APP_MSG_URL=http://$ALB_DNS:8006" \
  --build-arg "REACT_APP_ANALYTICS_URL=http://$ALB_DNS:8007" \
  --build-arg "REACT_APP_AI_URL=http://$ALB_DNS:8008" \
  -t "$FRONTEND_REPO:latest" \
  "$PROJECT_ROOT/frontend"
echo "==> Pushing frontend image…"
docker push "$FRONTEND_REPO:latest"

echo ""
echo "==> Images pushed successfully."
echo "    Backend:  $BACKEND_REPO:latest"
echo "    Frontend: $FRONTEND_REPO:latest"
echo ""
echo "==> Force-deploy frontend ECS service to pick up new image…"
CLUSTER="linkedin-sim"
aws ecs update-service --cluster "$CLUSTER" --service "${CLUSTER}-frontend" \
  --force-new-deployment --region "$REGION" > /dev/null
echo "    Done. Frontend will update in ~2 minutes."
