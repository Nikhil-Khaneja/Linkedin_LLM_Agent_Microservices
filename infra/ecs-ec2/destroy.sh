#!/usr/bin/env bash
# Tear down ECS demo: all linkedin-sim-* services, EC2, cluster. IAM roles unchanged by default.
set -euo pipefail

require_env() {
  local missing=()
  for v in "$@"; do
    if [[ -z "${!v:-}" ]]; then missing+=("$v"); fi
  done
  if ((${#missing[@]})); then
    echo "Missing required env: ${missing[*]}" >&2
    exit 1
  fi
}

export AWS_REGION="${AWS_REGION:?Set AWS_REGION}"
export PROJECT="${PROJECT:-linkedin-sim}"
export CLUSTER="${CLUSTER:-linkedin-sim-ec2}"
export SERVICE="${SERVICE:-linkedin-sim-service}"

require_env AWS_REGION

DELETE_ECR=0
for a in "$@"; do
  if [[ "$a" == "--delete-ecr" ]]; then DELETE_ECR=1; fi
done

echo "[destroy] CLUSTER=$CLUSTER REGION=$AWS_REGION"

# Delete all ECS services named linkedin-sim-* in this cluster
while read -r arn; do
  [[ -z "$arn" ]] && continue
  name="${arn##*/}"
  echo "[destroy] scaling down and deleting ECS service: $name"
  aws ecs update-service --cluster "$CLUSTER" --service "$name" --desired-count 0 --region "$AWS_REGION" >/dev/null 2>&1 || true
  aws ecs delete-service --cluster "$CLUSTER" --service "$name" --force --region "$AWS_REGION" >/dev/null 2>&1 || true
done < <(aws ecs list-services --cluster "$CLUSTER" --region "$AWS_REGION" --query 'serviceArns[*]' --output text 2>/dev/null | tr '\t' '\n' | grep 'linkedin-sim' || true)

# Legacy single-service name from older bootstrap docs
if [[ -n "$SERVICE" ]]; then
  aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" --desired-count 0 --region "$AWS_REGION" >/dev/null 2>&1 || true
  aws ecs delete-service --cluster "$CLUSTER" --service "$SERVICE" --force --region "$AWS_REGION" >/dev/null 2>&1 || true
fi

echo "[destroy] terminating EC2 instances tagged Name=linkedin-sim-ecs-ec2"
IIDS=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=linkedin-sim-ecs-ec2" "Name=instance-state-name,Values=running,stopped,stopping,pending" \
  --query 'Reservations[].Instances[].InstanceId' --output text --region "$AWS_REGION" || true)
if [[ -n "${IIDS// /}" ]]; then
  # shellcheck disable=SC2086
  aws ec2 terminate-instances --instance-ids $IIDS --region "$AWS_REGION" >/dev/null || true
else
  echo "[destroy] no matching EC2 instances"
fi

if aws ecs describe-clusters --clusters "$CLUSTER" --region "$AWS_REGION" --query 'clusters[0].clusterArn' --output text 2>/dev/null | grep -q '^arn:'; then
  echo "[destroy] deleting ECS cluster $CLUSTER"
  aws ecs delete-cluster --cluster "$CLUSTER" --region "$AWS_REGION" >/dev/null || true
else
  echo "[destroy] ECS cluster not found"
fi

if [[ "$DELETE_ECR" == 1 ]]; then
  echo "[destroy] deleting ECR repositories linkedin-sim/*"
  for r in \
    linkedin-sim/backend \
    linkedin-sim/auth_service \
    linkedin-sim/recruiter_company_service \
    linkedin-sim/member_profile_service \
    linkedin-sim/jobs_service \
    linkedin-sim/applications_service \
    linkedin-sim/messaging_connections_service \
    linkedin-sim/analytics_service \
    linkedin-sim/ai_orchestrator_service \
    linkedin-sim/frontend \
    linkedin-sim/mysql \
    linkedin-sim/mongo; do
    aws ecr delete-repository --repository-name "$r" --force --region "$AWS_REGION" >/dev/null 2>&1 || true
  done
else
  echo "[destroy] skipping ECR (pass --delete-ecr to remove repositories)"
fi

echo "[destroy] IAM roles were NOT deleted."
echo "Done."
