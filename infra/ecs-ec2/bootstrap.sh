#!/usr/bin/env bash
# One-time AWS bootstrap: ECS EC2 capacity, IAM, ECR, OIDC for GitHub Actions (no ECS service — first deploy via CI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

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

create_role_if_missing() {
  local role_name="$1" trust_doc="$2"
  if aws iam get-role --role-name "$role_name" >/dev/null 2>&1; then
    echo "[iam] role exists: $role_name"
    return 0
  fi
  echo "[iam] creating role: $role_name"
  aws iam create-role --role-name "$role_name" --assume-role-policy-document "$trust_doc" >/dev/null
}

attach_policy_if_missing() {
  local role_name="$1" policy_arn="$2"
  local attached
  attached=$(aws iam list-attached-role-policies --role-name "$role_name" --query "AttachedPolicies[?PolicyArn=='$policy_arn'].PolicyArn" --output text || true)
  if [[ -n "$attached" ]]; then
    return 0
  fi
  echo "[iam] attaching $policy_arn -> $role_name"
  aws iam attach-role-policy --role-name "$role_name" --policy-arn "$policy_arn" >/dev/null
}

create_ecr_repo_if_missing() {
  local repo="$1"
  if aws ecr describe-repositories --repository-names "$repo" >/dev/null 2>&1; then
    echo "[ecr] exists: $repo"
    return 0
  fi
  echo "[ecr] create: $repo"
  aws ecr create-repository --repository-name "$repo" >/dev/null
}

security_group_exists() {
  local name="$1" vpc="$2"
  aws ec2 describe-security-groups --filters "Name=group-name,Values=$name" "Name=vpc-id,Values=$vpc" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null | grep -q '^sg-'
}

wait_for_ecs_instance() {
  local deadline=$((SECONDS + 900))
  echo "[ecs] waiting for container instance in cluster $CLUSTER ..."
  while ((SECONDS < deadline)); do
    local n
    n=$(aws ecs list-container-instances --cluster "$CLUSTER" --query 'length(containerInstanceArns)' --output text 2>/dev/null || echo 0)
    if [[ "${n:-0}" =~ ^[1-9] ]]; then
      echo "[ecs] container instance registered."
      return 0
    fi
    sleep 10
  done
  echo "[ecs] timed out waiting for container instance" >&2
  return 1
}

export AWS_REGION="${AWS_REGION:?Set AWS_REGION}"
export PROJECT="${PROJECT:-linkedin-sim}"
export CLUSTER="${CLUSTER:-linkedin-sim-ec2}"
export INSTANCE_TYPE="${INSTANCE_TYPE:-t3.xlarge}"
export KEY_NAME="${KEY_NAME:-linkedin-sim-key}"
echo "[info] EC2 key pair name: $KEY_NAME (set KEY_NAME to reuse an existing pair; otherwise we create this name if missing)"

require_env GITHUB_OWNER GITHUB_REPO
export GITHUB_OWNER GITHUB_REPO

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_ACCOUNT_ID
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
MY_IP="$(curl -fsS --max-time 10 https://checkip.amazonaws.com)/32" || {
  echo "Could not determine public IP via checkip.amazonaws.com" >&2
  exit 1
}

echo "[info] AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID REGION=$AWS_REGION MY_IP=$MY_IP"

# --- SSH key pair ---
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "[ec2] key pair exists: $KEY_NAME"
else
  echo "[ec2] creating key pair $KEY_NAME -> ${KEY_NAME}.pem"
  aws ec2 create-key-pair --key-name "$KEY_NAME" --region "$AWS_REGION" --query KeyMaterial --output text >"${ROOT}/${KEY_NAME}.pem"
  chmod 400 "${ROOT}/${KEY_NAME}.pem"
  echo "Saved private key: ${ROOT}/${KEY_NAME}.pem"
fi

# --- IAM: ecsInstanceRole ---
ECS_INSTANCE_TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
create_role_if_missing ecsInstanceRole "$ECS_INSTANCE_TRUST"
attach_policy_if_missing ecsInstanceRole arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role
attach_policy_if_missing ecsInstanceRole arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

# --- IAM: ecsTaskExecutionRole ---
ECS_TASK_EXEC_TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
create_role_if_missing ecsTaskExecutionRole "$ECS_TASK_EXEC_TRUST"
attach_policy_if_missing ecsTaskExecutionRole arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# --- IAM: linkedinSimTaskRole ---
TASK_ROLE_TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
create_role_if_missing linkedinSimTaskRole "$TASK_ROLE_TRUST"

# --- IAM: instance profile ---
if ! aws iam get-instance-profile --instance-profile-name ecsInstanceProfile >/dev/null 2>&1; then
  echo "[iam] creating instance profile ecsInstanceProfile"
  aws iam create-instance-profile --instance-profile-name ecsInstanceProfile >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name ecsInstanceProfile --role-name ecsInstanceRole >/dev/null
else
  echo "[iam] instance profile ecsInstanceProfile exists"
  aws iam list-instance-profiles-for-role --role-name ecsInstanceRole --query 'InstanceProfiles[?InstanceProfileName==`ecsInstanceProfile`].InstanceProfileName' --output text | grep -q ecsInstanceProfile \
    || aws iam add-role-to-instance-profile --instance-profile-name ecsInstanceProfile --role-name ecsInstanceRole >/dev/null || true
fi

# --- OIDC provider for GitHub Actions ---
OIDC_URL="token.actions.githubusercontent.com"
if aws iam list-open-id-connect-providers --output text | grep -Fq "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_URL}"; then
  echo "[iam] OIDC provider exists"
else
  echo "[iam] creating OIDC provider github actions"
  aws iam create-open-id-connect-provider \
    --url "https://${OIDC_URL}" \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4e98bab03faadb97b34396831e3780aea1 1c58a3a8518e8759bf075b76b750d4f2df264fcd >/dev/null
fi

# --- githubActionsEcsDeployRole ---
GITHUB_TRUST=$(python3 -c "
import json, os
account = os.environ['AWS_ACCOUNT_ID']
sub = 'repo:' + os.environ['GITHUB_OWNER'] + '/' + os.environ['GITHUB_REPO'] + ':ref:refs/heads/main'
doc = {
  'Version': '2012-10-17',
  'Statement': [{
    'Effect': 'Allow',
    'Principal': {'Federated': f'arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com'},
    'Action': 'sts:AssumeRoleWithWebIdentity',
    'Condition': {
      'StringEquals': {'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com'},
      'StringLike': {'token.actions.githubusercontent.com:sub': sub},
    },
  }],
}
print(json.dumps(doc))
")
create_role_if_missing githubActionsEcsDeployRole "$GITHUB_TRUST"

DEPLOY_POLICY=$(python3 -c "
import json, os
account = os.environ['AWS_ACCOUNT_ID']
region = os.environ['AWS_REGION']
doc = {
  'Version': '2012-10-17',
  'Statement': [
    {'Effect': 'Allow', 'Action': ['sts:GetCallerIdentity'], 'Resource': '*'},
    {'Effect': 'Allow', 'Action': ['ecr:GetAuthorizationToken'], 'Resource': '*'},
    {'Effect': 'Allow', 'Action': ['ecr:BatchCheckLayerAvailability','ecr:CompleteLayerUpload','ecr:InitiateLayerUpload','ecr:PutImage','ecr:UploadLayerPart','ecr:BatchGetImage'],
     'Resource': f'arn:aws:ecr:{region}:{account}:repository/linkedin-sim/*'},
    {'Effect': 'Allow', 'Action': ['ecs:DescribeClusters','ecs:DescribeServices','ecs:DescribeTaskDefinition','ecs:DescribeTasks','ecs:ListTasks','ecs:RegisterTaskDefinition','ecs:UpdateService','ecs:CreateService','ecs:TagResource'], 'Resource': '*'},
    {'Effect': 'Allow', 'Action': ['iam:PassRole'], 'Resource': [
        f'arn:aws:iam::{account}:role/ecsTaskExecutionRole',
        f'arn:aws:iam::{account}:role/linkedinSimTaskRole',
    ]},
    {'Effect': 'Allow', 'Action': ['logs:CreateLogGroup','logs:DescribeLogGroups','logs:CreateLogStream','logs:PutLogEvents'], 'Resource': '*'},
  ],
}
print(json.dumps(doc))
")

aws iam put-role-policy --role-name githubActionsEcsDeployRole --policy-name linkedinSimEcsDeploy --policy-document "$DEPLOY_POLICY" >/dev/null
echo "[iam] updated inline policy linkedinSimEcsDeploy on githubActionsEcsDeployRole"

# --- ECR repositories (one repo per Python microservice + frontend + data images) ---
for r in \
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
  create_ecr_repo_if_missing "$r"
done

# --- ECS cluster ---
CLEN=$(aws ecs describe-clusters --clusters "$CLUSTER" --query 'length(clusters)' --output text 2>/dev/null || echo 0)
CST=$(aws ecs describe-clusters --clusters "$CLUSTER" --query 'clusters[0].status' --output text 2>/dev/null || echo "")
if [[ "${CLEN:-0}" != "0" && "$CST" == "ACTIVE" ]]; then
  echo "[ecs] cluster exists: $CLUSTER"
else
  echo "[ecs] creating cluster $CLUSTER"
  aws ecs create-cluster --cluster-name "$CLUSTER" >/dev/null || true
fi

# --- CloudWatch log group ---
if aws logs describe-log-groups --log-group-name-prefix "/ecs/linkedin-sim" --query "logGroups[?logGroupName=='/ecs/linkedin-sim'].logGroupName" --output text | grep -q '/ecs/linkedin-sim'; then
  echo "[logs] log group exists"
else
  echo "[logs] creating /ecs/linkedin-sim"
  aws logs create-log-group --log-group-name "/ecs/linkedin-sim" >/dev/null || true
fi

# --- Default VPC + subnet in an AZ that offers INSTANCE_TYPE ---
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
if [[ -z "$VPC_ID" || "$VPC_ID" == "None" ]]; then
  echo "No default VPC found in $AWS_REGION" >&2
  exit 1
fi

OFFER_AZS=$(aws ec2 describe-instance-type-offerings \
  --region "$AWS_REGION" \
  --location-type availability-zone \
  --filters "Name=instance-type,Values=${INSTANCE_TYPE}" \
  --query 'InstanceTypeOfferings[].Location' --output text 2>/dev/null | tr '\t' '\n' | sed '/^$/d' | sort -u || true)

SUBNET_ID=""
SUBNET_AZ=""
if [[ -n "${OFFER_AZS//[$' \t\n']/}" ]]; then
  while read -r sid saz; do
    [[ -z "$sid" || -z "$saz" ]] && continue
    if printf '%s\n' "$OFFER_AZS" | grep -qx "$saz"; then
      SUBNET_ID=$sid
      SUBNET_AZ=$saz
      break
    fi
  done < <(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[].[SubnetId,AvailabilityZone]' --output text --region "$AWS_REGION" | LC_ALL=C sort -k2,2)
fi

if [[ -z "$SUBNET_ID" ]]; then
  if [[ -n "${OFFER_AZS//[$' \t\n']/}" ]]; then
    echo "No default-VPC subnet found in an AZ that offers instance type $INSTANCE_TYPE." >&2
    echo "AZs that offer this type in $AWS_REGION:" >&2
    printf '%s\n' "$OFFER_AZS" | sed 's/^/  /' >&2
    exit 1
  fi
  echo "[warn] Could not list AZ offerings for $INSTANCE_TYPE; falling back to first subnet in VPC (launch may fail in unsupported AZs)" >&2
  SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[0].SubnetId' --output text --region "$AWS_REGION")
  SUBNET_AZ=$(aws ec2 describe-subnets --subnet-ids "$SUBNET_ID" --query 'Subnets[0].AvailabilityZone' --output text --region "$AWS_REGION")
fi

echo "[network] VPC=$VPC_ID SUBNET=$SUBNET_ID AZ=$SUBNET_AZ instance_type=$INSTANCE_TYPE"

SG_NAME="linkedin-sim-ecs-sg"
if security_group_exists "$SG_NAME" "$VPC_ID"; then
  SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")
  echo "[ec2] security group exists $SG_ID"
else
  echo "[ec2] creating security group $SG_NAME"
  SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" --description "linkedin-sim ECS EC2" --vpc-id "$VPC_ID" --region "$AWS_REGION" --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$MY_IP" --region "$AWS_REGION" >/dev/null
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0 --region "$AWS_REGION" >/dev/null
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 8001-8008 --cidr 0.0.0.0/0 --region "$AWS_REGION" >/dev/null
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 9000-9001 --cidr 0.0.0.0/0 --region "$AWS_REGION" >/dev/null
  # Allow tasks on the same SG to reach each other (bridge host ports on the instance).
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 1-65535 --source-group "$SG_ID" --region "$AWS_REGION" >/dev/null || true
fi

# --- ECS-optimized AL2023 AMI (x86_64 vs arm64 for Graviton families) ---
ecs_ami_ssm_param() {
  case "$INSTANCE_TYPE" in
  a1.*|c6g.*|c7g.*|m6g.*|m7g.*|r6g.*|r7g.*|t4g.*|i4g.*|im4g.*|is4ge.*|x2gd.*|g5g.*)
    echo "/aws/service/ecs/optimized-ami/amazon-linux-2023/arm64/recommended/image_id"
    ;;
  *)
    echo "/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id"
    ;;
  esac
}
AMI_SSM=$(ecs_ami_ssm_param)
echo "[ec2] ECS AMI SSM: $AMI_SSM (for instance type $INSTANCE_TYPE)"
AMI_ID=$(aws ssm get-parameter --name "$AMI_SSM" --query Parameter.Value --output text --region "$AWS_REGION")

UD_FILE=$(mktemp)
trap 'rm -f "$UD_FILE"' EXIT
cat >"$UD_FILE" <<EOF
#!/bin/bash
echo ECS_CLUSTER=${CLUSTER} >> /etc/ecs/ecs.config
echo ECS_ENABLE_CONTAINER_METADATA=true >> /etc/ecs/ecs.config
mkdir -p /ecs/linkedin-sim/mysql /ecs/linkedin-sim/mongo /ecs/linkedin-sim/redis /ecs/linkedin-sim/kafka /ecs/linkedin-sim/minio
chmod -R 777 /ecs/linkedin-sim || true
EOF

# --- Launch EC2 if none tagged ---
RUNNING=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=linkedin-sim-ecs-ec2" "Name=instance-state-name,Values=running,pending" \
  --query 'length(Reservations[].Instances[])' --output text --region "$AWS_REGION" || echo 0)
if [[ "${RUNNING:-0}" =~ ^[1-9] ]]; then
  echo "[ec2] instance already running (tag Name=linkedin-sim-ecs-ec2)"
else
  echo "[ec2] launching ECS instance type=$INSTANCE_TYPE (set INSTANCE_TYPE to override; t3.large is marginal for Kafka+DB+all apps)"
  RI_ERR=$(mktemp)
  if ! aws ec2 run-instances \
    --region "$AWS_REGION" \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --subnet-id "$SUBNET_ID" \
    --security-group-ids "$SG_ID" \
    --iam-instance-profile Name=ecsInstanceProfile \
    --associate-public-ip-address \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":60,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=linkedin-sim-ecs-ec2},{Key=Project,Value='"$PROJECT"'}]' \
    --user-data "file://$UD_FILE" >/dev/null 2>"$RI_ERR"; then
    cat "$RI_ERR" >&2
    if grep -qi 'Free Tier' "$RI_ERR"; then
      echo "" >&2
      echo "[bootstrap] AWS blocked this instance type under Free Tier rules (common on new or student accounts)." >&2
      echo "  • Preferred: finish account / billing setup so you can launch paid instances, then rerun (e.g. unset INSTANCE_TYPE for default t3.xlarge)." >&2
      echo "  • If you must stay on Free Tier–eligible sizes only, try a larger *eligible* type for your account date, e.g.:" >&2
      echo "      aws ec2 describe-instance-types --filters Name=free-tier-eligible,Values=true --query 'InstanceTypes[].InstanceType' --output text" >&2
      echo "    then: export INSTANCE_TYPE=t3.small   # still may be too small for Kafka+full stack" >&2
    fi
    rm -f "$RI_ERR"
    exit 1
  fi
  rm -f "$RI_ERR"
fi

INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=linkedin-sim-ecs-ec2" "Name=instance-state-name,Values=running,pending" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text --region "$AWS_REGION")

echo "[ec2] waiting for instance running: $INSTANCE_ID"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"

wait_for_ecs_instance

APP_HOST=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=linkedin-sim-ecs-ec2" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text --region "$AWS_REGION")

if [[ -z "$APP_HOST" || "$APP_HOST" == "None" ]]; then
  APP_HOST=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=linkedin-sim-ecs-ec2" "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].PublicDnsName' --output text --region "$AWS_REGION")
fi

ECS_HOST_PRIVATE_IP=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=linkedin-sim-ecs-ec2" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text --region "$AWS_REGION")

GITHUB_ACTIONS_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/githubActionsEcsDeployRole"

echo ""
echo "========== Bootstrap complete =========="
echo "AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID"
echo "AWS_REGION=$AWS_REGION"
echo "CLUSTER=$CLUSTER"
echo "APP_HOST=$APP_HOST"
echo "ECS_HOST_PRIVATE_IP=$ECS_HOST_PRIVATE_IP"
echo "Per-service backend ECR repos: ${ECR_BASE}/linkedin-sim/<auth_service|member_profile_service|...>"
echo "ECR_FRONTEND_REPO=${ECR_BASE}/linkedin-sim/frontend"
echo "ECR_MYSQL_REPO=${ECR_BASE}/linkedin-sim/mysql"
echo "ECR_MONGO_REPO=${ECR_BASE}/linkedin-sim/mongo"
echo "GITHUB_ACTIONS_ROLE_ARN=$GITHUB_ACTIONS_ROLE_ARN"
echo ""
echo "Set these GitHub Actions repository variables:"
echo "AWS_REGION=$AWS_REGION"
echo "AWS_ROLE_ARN=$GITHUB_ACTIONS_ROLE_ARN"
echo "ECS_CLUSTER=$CLUSTER"
echo "APP_HOST=$APP_HOST"
echo "ECS_HOST_PRIVATE_IP=$ECS_HOST_PRIVATE_IP"
echo "ECR_FRONTEND_REPOSITORY=linkedin-sim/frontend"
echo "ECR_MYSQL_REPOSITORY=linkedin-sim/mysql"
echo "ECR_MONGO_REPOSITORY=linkedin-sim/mongo"
echo ""
echo "OpenRouter (AI orchestrator on ECS): add a GitHub Actions *repository secret* (not a variable):"
echo "  GitHub → Settings → Secrets and variables → Actions → New repository secret"
echo "  Name:  OPENROUTER_API_KEY"
echo "  Value: your OpenRouter key (e.g. sk-or-...)"
echo "Then run Deploy ECS EC2 again (or push a change under backend/services/ai_orchestrator_service/) so task defs pick up the key."
echo ""
echo "ECS services are NOT created here. Push to main (or workflow_dispatch) after variables are set."
echo "Use multi-service deploy: one ECS service per app + linkedin-sim-platform (data). Set ECS_HOST_PRIVATE_IP in GitHub variables."
