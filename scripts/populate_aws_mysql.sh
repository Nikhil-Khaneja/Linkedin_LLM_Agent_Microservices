#!/usr/bin/env bash
# One-shot: find the linkedin-sim EC2 instance, open an SSH tunnel to MySQL, run bulk seed.
# Run from your laptop (same network/IP allowed by the instance security group for SSH).
#
# Usage:
#   ./scripts/populate_aws_mysql.sh
# Optional:
#   export AWS_REGION=us-east-1
#   export EC2_KEY=./linkedin-sim-key.pem
#   export EC2_USER=ec2-user          # or ubuntu
#   export BULK_SEED_RUN_ID=aws1
#   cp .env.aws.mysql.example .env.aws.mysql   # if you need a non-default MySQL password

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REGION="${AWS_REGION:-us-east-1}"
KEY="${EC2_KEY:-$ROOT/linkedin-sim-key.pem}"
USER="${EC2_USER:-ec2-user}"
LOCAL_PORT="${MYSQL_TUNNEL_LOCAL_PORT:-3307}"
RUN_ID="${BULK_SEED_RUN_ID:-aws1}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI not found. Install AWS CLI v2 and configure credentials." >&2
  exit 1
fi

IP="$(
  aws ec2 describe-instances --region "$REGION" \
    --filters "Name=instance-state-name,Values=running" "Name=tag:Project,Values=linkedin-sim" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text 2>/dev/null || true
)"
if [[ -z "$IP" || "$IP" == "None" ]]; then
  echo "No running instance with tag Project=linkedin-sim in $REGION." >&2
  echo "Set EC2_PUBLIC_IP manually: export EC2_PUBLIC_IP=x.x.x.x && $0" >&2
  exit 1
fi
if [[ -n "${EC2_PUBLIC_IP:-}" ]]; then
  IP="$EC2_PUBLIC_IP"
fi

if [[ ! -f "$KEY" ]]; then
  echo "SSH key not found: $KEY" >&2
  exit 1
fi
chmod 400 "$KEY" 2>/dev/null || true

if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "$LOCAL_PORT" 2>/dev/null; then
  echo "Port $LOCAL_PORT already in use (tunnel may already be running)."
else
  echo "Starting SSH tunnel: 127.0.0.1:$LOCAL_PORT -> $IP:3306 (MySQL on EC2) ..."
  ssh -f -N -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 \
    -i "$KEY" -L "${LOCAL_PORT}:127.0.0.1:3306" "${USER}@${IP}"
  sleep 2
fi

export MYSQL_HOST=127.0.0.1
export MYSQL_PORT="$LOCAL_PORT"
export MYSQL_USER="${MYSQL_USER:-root}"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-root}"
export MYSQL_DATABASE="${MYSQL_DATABASE:-linkedin_sim}"

if [[ -f .env.aws.mysql ]]; then
  echo "Loading .env.aws.mysql (overrides defaults above for matching keys)."
  set -a
  # shellcheck disable=1091
  source "$ROOT/.env.aws.mysql"
  set +a
fi

export BULK_SEED_RUN_ID="$RUN_ID"
exec "$ROOT/scripts/bulk_seed_aws_mysql.sh"
