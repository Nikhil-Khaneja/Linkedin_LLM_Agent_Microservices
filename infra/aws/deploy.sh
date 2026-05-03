#!/usr/bin/env bash
# Full AWS ECS deployment
# Prerequisites: aws cli configured, terraform >= 1.3, docker
# Usage: ./deploy.sh [--destroy]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${1:-}" == "--destroy" ]]; then
  echo "==> Destroying AWS infrastructure…"
  terraform destroy -auto-approve
  exit 0
fi

# ── Step 1: Terraform apply (creates VPC, RDS, Redis, ECS cluster, ALB, ECR) ─
echo "==> [1/4] Initialising Terraform…"
terraform init -upgrade

echo "==> [2/4] Applying infrastructure (this takes ~10 minutes for RDS)…"
terraform apply -auto-approve

ALB_DNS=$(terraform output -raw alb_dns_name)
echo ""
echo "    ALB DNS: $ALB_DNS"
echo "    Frontend will be: http://$ALB_DNS"
echo ""

# ── Step 2: Build and push Docker images ─────────────────────────────────────
echo "==> [3/4] Building and pushing Docker images to ECR…"
bash push_images.sh

# ── Step 3: Force re-deploy all ECS services ─────────────────────────────────
echo "==> [4/4] Force-deploying all ECS services…"
REGION=${AWS_DEFAULT_REGION:-us-east-1}
CLUSTER="linkedin-sim"
SERVICES=(
  auth_service member_profile_service recruiter_company_service
  jobs_service applications_service messaging_connections_service
  analytics_service ai_orchestrator_service frontend
)
for svc in "${SERVICES[@]}"; do
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "${CLUSTER}-${svc}" \
    --force-new-deployment \
    --region "$REGION" > /dev/null
  echo "    Deployed: $svc"
done

echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│  Deployment complete!                                        │"
echo "│                                                              │"
echo "│  Frontend:   http://$ALB_DNS"
echo "│  Auth:       http://$ALB_DNS:8001"
echo "│  Jobs:       http://$ALB_DNS:8004"
echo "│  Analytics:  http://$ALB_DNS:8007"
echo "│  MinIO:      http://$ALB_DNS:9000"
echo "│                                                              │"
echo "│  Services take ~3-5 min to pass health checks.              │"
echo "│  Monitor: aws ecs describe-services --cluster $CLUSTER       │"
echo "└─────────────────────────────────────────────────────────────┘"
