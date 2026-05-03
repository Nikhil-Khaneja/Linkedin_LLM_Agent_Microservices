# AWS Deployment — Step-by-Step Guide

**Author:** Person 4 (Sanjay)
**Updated:** 2026-05-02

This guide deploys the full LinkedIn Simulation stack to AWS using a single EC2 instance with Docker Compose. This is the zero-cost-friendly approach — all services run inside containers on one host, fronted by Nginx as a reverse proxy.

---

## Architecture

```
Internet
    │
    ▼
EC2 Instance (t2.micro or t3.micro, free tier)
    │
    ▼
Nginx (port 80/443)  ←── reverse proxy
    │
    ├── /api/auth/*        → auth_service:8001
    ├── /api/members/*     → member_profile_service:8002
    ├── /api/recruiters/*  → recruiter_company_service:8003
    ├── /api/jobs/*        → jobs_service:8004
    ├── /api/applications/*→ applications_service:8005
    ├── /api/messages/*    → messaging_connections_service:8006
    ├── /api/analytics/*   → analytics_service:8007
    ├── /api/ai/*          → ai_orchestrator_service:8008
    ├── /ws/ai/*           → ai_orchestrator_service:8008 (WebSocket)
    └── /*                 → React frontend (Nginx static or port 5173)

Inside Docker Compose (same host):
    MySQL:8001, MongoDB:27017, Redis:6379, Kafka KRaft:9092
    MinIO:9000, Prometheus:9090, Grafana:3000
```

---

## Step 1 — Launch an EC2 Instance

1. Go to **AWS Console → EC2 → Launch Instance**
2. Select **Amazon Linux 2023** (or Ubuntu 22.04) AMI
3. Choose instance type: `t2.micro` (free tier) or `t3.small` if available
4. **Storage:** increase root volume to **30 GB** (Docker images are large)
5. **Security Group** — open these inbound ports:

| Port | Protocol | Source | Purpose |
|---|---|---|---|
| 22 | TCP | Your IP | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP (Nginx) |
| 443 | TCP | 0.0.0.0/0 | HTTPS (optional) |
| 5173 | TCP | 0.0.0.0/0 | React frontend direct (optional) |
| 8001-8008 | TCP | 0.0.0.0/0 | Backend services direct (optional) |

6. Create or select an **SSH key pair** and download `.pem` file
7. Launch the instance and note the **Public IPv4 address**

---

## Step 2 — SSH Into the Instance

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ec2-user@<PUBLIC_IP>
# Ubuntu: ssh -i your-key.pem ubuntu@<PUBLIC_IP>
```

---

## Step 3 — Install Docker and Docker Compose

```bash
# Amazon Linux 2023
sudo dnf update -y
sudo dnf install -y docker git

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user
newgrp docker

# Install Docker Compose plugin
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
     -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Verify
docker compose version
```

For **Ubuntu** replace `dnf` with `apt-get` and `docker` package with `docker.io`:
```bash
sudo apt-get update -y
sudo apt-get install -y docker.io git
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker ubuntu && newgrp docker
```

---

## Step 4 — Clone the Repository

```bash
cd ~
git clone https://github.com/<your-org>/Linkedin_Prototype_LLM_Agent_Microservices.git
cd Linkedin_Prototype_LLM_Agent_Microservices
```

---

## Step 5 — Configure Environment Variables

```bash
cp .env.example .env
nano .env   # or: vim .env
```

Required values to set (everything else can stay as default):

```bash
# JWT — MUST match across all services
JWT_ISSUER=owner1-auth
JWT_AUDIENCE=linkedin-clone

# MySQL — stays as default inside Docker
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=linkedin_sim
MYSQL_USER=root
MYSQL_PASSWORD=root

# MongoDB
MONGO_URL=mongodb://mongo:27017
MONGO_DATABASE=linkedin_sim_docs

# Redis
CACHE_MODE=redis
REDIS_URL=redis://redis:6379/0

# Kafka (KRaft inside Docker)
EVENT_BUS_MODE=kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# MinIO (object storage)
MINIO_ENDPOINT=minio:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET_PROFILE=profile-media

# Frontend — update with your EC2 public IP
VITE_API_BASE_URL=http://<PUBLIC_IP>
MINIO_PUBLIC_ENDPOINT=<PUBLIC_IP>:9000

# OpenRouter (AI outreach generation — optional for demo)
OPENROUTER_API_KEY=sk-or-...
```

---

## Step 6 — Build and Start All Services

```bash
# Build images and start in detached mode
docker compose up -d --build

# Monitor startup (takes 2-3 minutes first time)
docker compose logs -f --tail=50
```

Wait until you see all services healthy:
```bash
docker compose ps
# All services should show "healthy" or "running"
```

---

## Step 7 — Initialize the Database

```bash
# Apply MySQL schema (creates all tables)
./scripts/apply_mysql_schema.sh

# Create Kafka topics
./scripts/create_kafka_topics.sh

# Initialize MongoDB indexes
./scripts/apply_mongo_init.sh

# Seed demo data (optional — 10,000+ records for benchmarking)
python3 scripts/seed_perf_data.py --jobs 10000 --members 10000
```

---

## Step 8 — Install and Configure Nginx

```bash
# Amazon Linux 2023
sudo dnf install -y nginx

# Ubuntu
sudo apt-get install -y nginx
```

Create the Nginx config:
```bash
sudo nano /etc/nginx/conf.d/linkedin_sim.conf
```

Paste this configuration:

```nginx
server {
    listen 80;
    server_name _;

    # Health check
    location /health {
        return 200 'ok';
        add_header Content-Type text/plain;
    }

    # Auth service
    location /api/auth/ {
        proxy_pass http://localhost:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Trace-Id $http_x_trace_id;
    }

    # Member profile service
    location /api/members/ {
        proxy_pass http://localhost:8002/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Trace-Id $http_x_trace_id;
    }

    # Recruiter / company service
    location /api/recruiters/ {
        proxy_pass http://localhost:8003/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Trace-Id $http_x_trace_id;
    }

    # Jobs service
    location /api/jobs/ {
        proxy_pass http://localhost:8004/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Trace-Id $http_x_trace_id;
        proxy_set_header Idempotency-Key $http_idempotency_key;
    }

    # Applications service
    location /api/applications/ {
        proxy_pass http://localhost:8005/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Trace-Id $http_x_trace_id;
        proxy_set_header Idempotency-Key $http_idempotency_key;
    }

    # Messaging + connections service
    location /api/messages/ {
        proxy_pass http://localhost:8006/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Trace-Id $http_x_trace_id;
        proxy_set_header Idempotency-Key $http_idempotency_key;
    }

    # Analytics service
    location /api/analytics/ {
        proxy_pass http://localhost:8007/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Trace-Id $http_x_trace_id;
    }

    # AI orchestrator service
    location /api/ai/ {
        proxy_pass http://localhost:8008/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Trace-Id $http_x_trace_id;
    }

    # WebSocket for AI tasks
    location /ws/ai/ {
        proxy_pass http://localhost:8008/ws/ai/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_read_timeout 86400;
    }

    # React frontend
    location / {
        proxy_pass http://localhost:5173/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Start Nginx:
```bash
sudo nginx -t           # test config
sudo systemctl enable nginx
sudo systemctl start nginx
```

---

## Step 9 — Verify Deployment

```bash
# Check all services are healthy
curl http://localhost:8001/ops/healthz
curl http://localhost:8004/ops/healthz
curl http://localhost:8007/ops/healthz

# Check Redis cache stats
curl http://localhost:8004/ops/cache-stats

# Check Kafka topics
docker exec -it $(docker compose ps -q kafka) \
  kafka-topics.sh --bootstrap-server localhost:9092 --list

# Test a public endpoint
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"member1@seed.example.com","password":"seeded"}'
```

Open in browser: `http://<PUBLIC_IP>` → you should see the LinkedIn Sim login page.

---

## Step 10 — Multi-Replica Deployment (B+S+K+Other Config)

To test horizontal scaling for the benchmark:

```bash
# Scale jobs and applications services to 2 replicas
docker compose up -d --scale jobs_service=2 --scale applications_service=2

# Verify both containers are running
docker compose ps

# Verify Kafka consumer group has 2 consumers
docker exec -it $(docker compose ps -q kafka) \
  kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group applications_service
```

Expected output shows 2 members, each assigned different partition ranges.

---

## Step 11 — Run Performance Benchmarks on AWS

```bash
# Install Python deps
pip3 install requests --break-system-packages

# Run all 4 configs (sequential)
python3 scripts/run_performance_benchmarks.py --all \
  --analytics-base http://localhost:8007 \
  --jobs-base http://localhost:8004 \
  --app-base http://localhost:8005

# Results stored in MongoDB, visible in AnalyticsPage
open http://<PUBLIC_IP>  # → Analytics tab → Benchmark Charts
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `docker compose up` fails — port already in use | `sudo lsof -i :<port>` then kill the process |
| MySQL schema not found | Run `./scripts/apply_mysql_schema.sh` after compose is up |
| Kafka topics missing | Run `./scripts/create_kafka_topics.sh` |
| Services can't reach each other | Use Docker service names (`kafka:9092`, `mysql:3306`) not `localhost` — check `.env` |
| CORS errors in browser | Verify `REACT_APP_*` env vars point to correct IP; CORS is locked to `localhost:5173` by default |
| `ops/healthz` returns 502 | Service hasn't started yet — wait 30s and retry |
| Nginx 502 Bad Gateway | Backend service container crashed — check `docker compose logs <service>` |

---

## Appendix — ECS Task Definitions (Full ECS/Fargate Deployment)

ECS task definition JSON files are located in:
```
deploy/aws_accounts/ecs_task_definitions/
  auth_service.json
  member_profile_service.json
  recruiter_company_service.json
  jobs_service.json
  applications_service.json
  messaging_connections_service.json
  analytics_service.json
  ai_orchestrator_service.json
```

Each task definition is pre-configured for **Fargate** with 512 CPU / 1024 MB memory, health check on `/ops/healthz`, and CloudWatch logging. To register and deploy:

```bash
# Set your AWS account variables
export AWS_ACCOUNT_ID=123456789012
export AWS_REGION=us-east-1

# 1. Create ECR repository (one-time)
aws ecr create-repository --repository-name linkedin-sim-backend --region $AWS_REGION

# 2. Build and push Docker image
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker build -t linkedin-sim-backend ./backend
docker tag linkedin-sim-backend:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/linkedin-sim-backend:latest
docker push \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/linkedin-sim-backend:latest

# 3. Register all 8 task definitions
for svc in auth_service member_profile_service recruiter_company_service \
           jobs_service applications_service messaging_connections_service \
           analytics_service ai_orchestrator_service; do
  # substitute real values for placeholders
  sed -e "s/\${AWS_ACCOUNT_ID}/$AWS_ACCOUNT_ID/g" \
      -e "s/\${AWS_REGION}/$AWS_REGION/g" \
      -e "s/\${KAFKA_BOOTSTRAP_SERVERS}/$KAFKA_BOOTSTRAP_SERVERS/g" \
      -e "s/\${REDIS_URL}/$REDIS_URL/g" \
      -e "s/\${MYSQL_HOST}/$MYSQL_HOST/g" \
      -e "s/\${MYSQL_USER}/root/g" \
      -e "s/\${MYSQL_PASSWORD}/$MYSQL_PASSWORD/g" \
      -e "s/\${MONGO_URL}/$MONGO_URL/g" \
      -e "s/\${OWNER1_JWKS_URL}/$OWNER1_JWKS_URL/g" \
      -e "s/\${MINIO_ENDPOINT}/$MINIO_ENDPOINT/g" \
      -e "s/\${MINIO_ROOT_USER}/minioadmin/g" \
      -e "s/\${MINIO_ROOT_PASSWORD}/minioadmin/g" \
      deploy/aws_accounts/ecs_task_definitions/${svc}.json > /tmp/${svc}_resolved.json
  aws ecs register-task-definition --cli-input-json file:///tmp/${svc}_resolved.json
  echo "Registered task definition: $svc"
done

# 4. Create ECS cluster
aws ecs create-cluster --cluster-name linkedin-sim

# 5. Create a service per task definition (with ALB target group)
# Replace <TARGET_GROUP_ARN_*> with ARNs from your ALB setup
for svc in auth_service member_profile_service recruiter_company_service \
           jobs_service applications_service messaging_connections_service \
           analytics_service ai_orchestrator_service; do
  aws ecs create-service \
    --cluster linkedin-sim \
    --service-name $svc \
    --task-definition $svc \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_ID>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}"
  echo "Created ECS service: $svc"
done
```

**Environment variables for managed AWS services:**

| Variable | AWS Service |
|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | Amazon MSK broker endpoint |
| `MYSQL_HOST` | RDS Aurora MySQL endpoint |
| `MONGO_URL` | DocumentDB cluster endpoint |
| `REDIS_URL` | ElastiCache Redis endpoint |

> For a class demo with near-zero cost, use the Docker Compose on EC2 approach (Steps 1–11 above) and reference these ECS files to show the deployment architecture.


| Resource | Monthly Cost |
|---|---|
| EC2 t2.micro (750 hrs free tier) | $0 (free tier) |
| EBS 30 GB gp2 | ~$3/month |
| Data transfer out (demo usage) | < $1/month |
| **Total (demo period)** | **~$0–4/month** |

For strictly zero cost: use an AWS Academy sandbox account or stop the instance after demo.
