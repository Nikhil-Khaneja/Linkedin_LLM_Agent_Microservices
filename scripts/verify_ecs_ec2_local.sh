#!/usr/bin/env bash
# Local checks for ECS-on-EC2 path (no AWS calls). Run from repo root: ./scripts/verify_ecs_ec2_local.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Shell syntax (bootstrap / destroy)"
bash -n infra/ecs-ec2/bootstrap.sh
bash -n infra/ecs-ec2/destroy.sh

echo "==> Python syntax (render / deploy)"
python3 -c "import ast; ast.parse(open('infra/ecs-ec2/render_taskdefs.py', encoding='utf-8').read())"
python3 -c "import ast; ast.parse(open('infra/ecs-ec2/deploy_services.py', encoding='utf-8').read())"

echo "==> ECS task definition template JSON"
python3 -c "import json; json.load(open('infra/ecs-ec2/ecs-taskdef.template.json', encoding='utf-8')); print('OK')"

echo "==> render_taskdefs.py (dummy images, single BACKEND_IMAGE fallback)"
export AWS_REGION=us-east-1 AWS_ACCOUNT_ID=000000000000 APP_HOST=1.2.3.4 ECS_HOST_PRIVATE_IP=10.0.0.5
export FRONTEND_IMAGE=example.invalid/frontend:tag MYSQL_IMAGE=example.invalid/mysql:tag MONGO_IMAGE=example.invalid/mongo:tag
export BACKEND_IMAGE=example.invalid/backend:tag OPENROUTER_API_KEY=
python3 infra/ecs-ec2/render_taskdefs.py
python3 -c "import json; j=json.load(open('infra/ecs-ec2/rendered/taskdef-auth_service.json')); assert j['containerDefinitions'][0]['image']=='example.invalid/backend:tag'"

echo "==> render_taskdefs.py (per-service env vars)"
unset BACKEND_IMAGE
export BACKEND_IMAGE_AUTH_SERVICE=a BACKEND_IMAGE_RECRUITER_COMPANY_SERVICE=b BACKEND_IMAGE_MEMBER_PROFILE_SERVICE=c
export BACKEND_IMAGE_JOBS_SERVICE=d BACKEND_IMAGE_APPLICATIONS_SERVICE=e BACKEND_IMAGE_MESSAGING_CONNECTIONS_SERVICE=f
export BACKEND_IMAGE_ANALYTICS_SERVICE=g BACKEND_IMAGE_AI_ORCHESTRATOR_SERVICE=h
python3 infra/ecs-ec2/render_taskdefs.py
python3 -c "import json; j=json.load(open('infra/ecs-ec2/rendered/taskdef-jobs_service.json')); assert j['containerDefinitions'][0]['image']=='d'"

if command -v docker >/dev/null 2>&1; then
  echo "==> docker compose config"
  docker compose config -q
  echo "==> docker build --target auth_service (may take a minute on first run)"
  docker build -q --target auth_service -t linkedin-sim-verify-auth:local ./backend
else
  echo "==> docker not found; skipping compose config and image build"
fi

echo ""
echo "All local ECS-on-EC2 checks passed."
echo ""
echo "You still need to do (with your AWS account + GitHub repo):"
echo "  1) export GITHUB_OWNER=... GITHUB_REPO=... AWS_REGION=... CLUSTER=... KEY_NAME=..."
echo "  2) bash infra/ecs-ec2/bootstrap.sh   # creates 8 backend ECR repos + front/mysql/mongo, OIDC role, EC2, …"
echo "  3) In GitHub → Settings → Variables: set AWS_REGION, AWS_ROLE_ARN, ECS_CLUSTER, APP_HOST,"
echo "     ECS_HOST_PRIVATE_IP, ECR_FRONTEND_REPOSITORY, ECR_MYSQL_REPOSITORY, ECR_MONGO_REPOSITORY"
echo "     (remove ECR_BACKEND_REPOSITORY if it still exists from the old single-backend setup)."
echo "  4) Push to main or run Actions → Deploy ECS EC2 manually."
echo "  5) Optional: delete legacy ECR repo linkedin-sim/backend after a successful deploy."
