#!/usr/bin/env bash
# Run this script ON the EC2 instance (Amazon Linux 2 or Ubuntu 22.04).
# It installs k3s (lightweight Kubernetes), Docker, and kubectl.
#
# Usage (from your local machine):
#   ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP> "bash -s" < scripts/ec2-setup.sh
#
# Or copy this file to the instance first:
#   scp -i your-key.pem scripts/ec2-setup.sh ec2-user@<EC2_PUBLIC_IP>:~/
#   ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP> "chmod +x ~/ec2-setup.sh && ~/ec2-setup.sh"

set -euo pipefail

echo "==> Detecting OS"
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS=$ID
else
  OS="unknown"
fi

echo "==> Installing Docker"
if ! command -v docker &>/dev/null; then
  if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
    apt-get update -y
    apt-get install -y docker.io
    systemctl enable --now docker
  else
    # Amazon Linux 2 / AL2023
    yum update -y
    yum install -y docker
    systemctl enable --now docker
  fi
  usermod -aG docker "$USER" || true
fi
echo "Docker: $(docker --version)"

echo "==> Installing k3s"
if ! command -v k3s &>/dev/null; then
  curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
fi

echo "==> Waiting for k3s to be ready"
until k3s kubectl get nodes 2>/dev/null | grep -q "Ready"; do
  sleep 3
done
echo "k3s node ready"

echo "==> Configuring kubectl for current user"
mkdir -p "$HOME/.kube"
cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
chown "$(id -u):$(id -g)" "$HOME/.kube/config"
export KUBECONFIG="$HOME/.kube/config"

echo "==> k3s version: $(k3s --version | head -1)"
echo ""
echo "Setup complete. Run deploy.sh next to apply the k8s manifests."
echo "  export KUBECONFIG=\$HOME/.kube/config"
