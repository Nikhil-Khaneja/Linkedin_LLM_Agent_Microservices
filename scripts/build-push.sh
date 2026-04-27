#!/usr/bin/env bash
# Build and push Docker images to Docker Hub.
# Usage: ./scripts/build-push.sh <dockerhub-username> [tag]
#
# Example:
#   ./scripts/build-push.sh nikhilkhaneja latest
#   ./scripts/build-push.sh nikhilkhaneja v1.0.0

set -euo pipefail

DOCKER_USER="${1:?Usage: $0 <dockerhub-username> [tag]}"
TAG="${2:-latest}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

API_IMAGE="$DOCKER_USER/owner7-analytics-api:$TAG"
FRONTEND_IMAGE="$DOCKER_USER/owner7-frontend:$TAG"

echo "==> Building $API_IMAGE"
docker build \
  -f "$PROJECT_ROOT/Dockerfile.prod" \
  -t "$API_IMAGE" \
  "$PROJECT_ROOT"

echo "==> Building $FRONTEND_IMAGE"
docker build \
  --build-arg REACT_APP_ANALYTICS_URL=/analytics-api \
  -f "$PROJECT_ROOT/frontend/Dockerfile" \
  -t "$FRONTEND_IMAGE" \
  "$PROJECT_ROOT/frontend"

echo "==> Pushing $API_IMAGE"
docker push "$API_IMAGE"

echo "==> Pushing $FRONTEND_IMAGE"
docker push "$FRONTEND_IMAGE"

echo ""
echo "Done. Update k8s/05-analytics-api.yaml and k8s/06-frontend.yaml"
echo "  image: $API_IMAGE"
echo "  image: $FRONTEND_IMAGE"
