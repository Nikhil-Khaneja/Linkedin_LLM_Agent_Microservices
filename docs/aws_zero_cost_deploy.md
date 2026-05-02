# AWS deployment steps with the zero-cost reality check

The class brief asks for Docker deployment on AWS and mentions Kubernetes/ECS. The uploaded project brief also calls out Docker/AWS deployment and performance testing. However, a truly zero-cost production-style deployment is not always possible on AWS depending on your account status and service choices.

## What AWS currently says

- New AWS customers can use the Free Tier for up to 6 months and receive up to $200 in credits; always-free offers still exist for some services. AWS also requires a valid payment method for signup. See the current AWS Free Tier FAQs. citeturn845805view1
- EC2 free-tier benefits differ based on account creation date. Accounts created on or after July 15, 2025 get a 6-month free period/credits model rather than the older 12-month model. AWS documents the free-tier-eligible instance families and the changed policy. citeturn845805view0turn845805view1
- Amazon ECS itself has no extra charge on EC2 launch type, but you still pay for the EC2/EBS resources you run. Fargate is pay-per-vCPU/memory and is not zero-cost by default. citeturn848005view0turn848005view1
- Amazon MSK charges hourly for brokers plus storage, so it is not a zero-cost choice for a class demo. citeturn848005view2
- Lightsail currently offers a free trial on select bundles, but only for a limited period and still requires careful usage control. citeturn845805view2

## Best zero-cost-ish path for this project

For the class demo, the cheapest practical AWS path is:

1. Use one free-tier-eligible EC2 instance or a free-trial Lightsail instance.
2. Run Docker Compose on that single host.
3. Run Kafka locally in containers instead of MSK.
4. Run all services behind one reverse proxy like Nginx or Caddy.
5. Serve the React app either from the same host or from S3 static hosting.

This keeps the architecture faithful enough for the course while avoiding paid managed services.

## Option A: single EC2 instance with Docker Compose

### 1. Launch instance
- Pick a free-tier-eligible Linux AMI in your region.
- Use a free-tier-eligible instance type for your account.
- Open ports 22, 80, 443, 5173 (optional), and 8001-8008 only if you do not front them with Nginx.

### 2. Install Docker
```bash
sudo dnf update -y || sudo apt-get update -y
sudo dnf install -y docker git || sudo apt-get install -y docker.io git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user || sudo usermod -aG docker ubuntu
newgrp docker
```

### 3. Install Docker Compose plugin
```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

### 4. Deploy code
```bash
git clone <your-repo>
cd linkedin_sim_monorepo
cp .env.example .env
docker compose up -d --build
```

### 5. Put Nginx in front
Use a single domain like `yourhost.example.com` and proxy:
- `/api/auth` -> owner1:8001
- `/api/members` -> owner2:8002
- `/api/recruiters` -> owner3:8003
- `/api/jobs` -> owner4:8004
- `/api/applications` -> owner5:8005
- `/api/messages` -> owner6:8006
- `/api/analytics` -> owner7:8007
- `/api/ai` -> owner8:8008
- `/ws/ai` -> owner8 websocket

### 6. Add TLS
Use Caddy or Nginx + Certbot.

## Option B: static frontend on S3 + CloudFront, APIs on EC2

This reduces load on the EC2 instance but may still use billable services if you exceed the Free Tier/credit limits.

## What not to use if you want near-zero cost

- MSK for Kafka
- Fargate for all 8 containers
- separate RDS + DocumentDB + ElastiCache for a class demo

## Assignment compliance note

If your instructor strictly checks for ECS/Kubernetes, mention in your report that the zero-cost deployment uses Docker Compose on EC2 to preserve service boundaries while avoiding managed-service spend, and show containerized deployment evidence.
