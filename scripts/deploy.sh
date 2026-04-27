#!/usr/bin/env bash
# Deploy owner7 to a Kubernetes cluster (k3s on EC2 or any cluster).
# Usage: ./scripts/deploy.sh <dockerhub-username> [tag]
#
# Run from your local machine (requires kubectl pointing at the cluster),
# OR copy this repo to the EC2 instance and run it there.
#
# Steps performed:
#   1. Substitutes YOUR_DOCKERHUB_USER placeholder in manifests
#   2. Applies all k8s manifests in order
#   3. Waits for deployments to roll out
#   4. Prints the access URL

set -euo pipefail

DOCKER_USER="${1:?Usage: $0 <dockerhub-username> [tag]}"
TAG="${2:-latest}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")/k8s"

API_IMAGE="$DOCKER_USER/owner7-analytics-api:$TAG"
FRONTEND_IMAGE="$DOCKER_USER/owner7-frontend:$TAG"

echo "==> Applying manifests with images:"
echo "    API:      $API_IMAGE"
echo "    Frontend: $FRONTEND_IMAGE"

# Apply manifests, substituting the placeholder image names
for manifest in "$K8S_DIR"/*.yaml; do
  sed \
    -e "s|YOUR_DOCKERHUB_USER/owner7-analytics-api:latest|$API_IMAGE|g" \
    -e "s|YOUR_DOCKERHUB_USER/owner7-frontend:latest|$FRONTEND_IMAGE|g" \
    "$manifest" | kubectl apply -f -
done

echo "==> Waiting for deployments to be ready (timeout 5 min)"
kubectl rollout status deployment/redpanda   -n owner7 --timeout=300s
kubectl rollout status deployment/mongodb    -n owner7 --timeout=300s
kubectl rollout status deployment/redis      -n owner7 --timeout=300s
kubectl rollout status deployment/analytics-api -n owner7 --timeout=300s
kubectl rollout status deployment/frontend   -n owner7 --timeout=300s

echo ""
echo "==> All deployments ready."
echo ""

NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}' 2>/dev/null || echo "")
if [ -z "$NODE_IP" ]; then
  NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
fi

echo "Access the app at:"
echo "  Frontend:     http://$NODE_IP:30080"
echo "  API docs:     (via kubectl port-forward)"
echo "    kubectl port-forward svc/analytics-api 8000:8000 -n owner7"
