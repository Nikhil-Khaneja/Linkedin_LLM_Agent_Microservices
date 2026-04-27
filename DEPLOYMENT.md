# Deployment Guide

LinkedIn Simulation — 8-service distributed platform.

---

## Architecture

```
                          ┌──────────────────────┐
                          │   React Frontend      │
                          │   (nginx, port 3000)  │
                          └──────┬───────────────┘
                                 │ direct API calls per service
      ┌──────────┬──────────┬────┴──────┬──────────┬──────────┬──────────┬──────────┐
      ▼          ▼          ▼           ▼          ▼          ▼          ▼          ▼
  :8001       :8002       :8003       :8004       :8005       :8006      :8007      :8008
  Auth       Member    Recruiter     Job        Apply      Message   Analytics    AI
 (Owner1)   (Owner2)   (Owner3)    (Owner4)   (Owner5)   (Owner6)   (Owner7)  (Owner8)
    │           │          │           │          │          │          │
    └───────────┴──────────┴───────────┴──────────┴──────────┴──────────┘
                                       │
                              Kafka (Owner 7 EC2)
                              port 9092 (internal)
                              port 29092 (external)
```

**Auth:** Owner 1 issues RS256 JWTs. Services 2, 4, 5, 8 validate tokens via `GET /auth/jwks` on Owner 1.  
**Events:** All services publish domain events to Kafka. Owner 7 consumes all topics for analytics.

---

## Service Map

| Owner | Service | Stack | Internal Port | EC2 Host Port |
|---|---|---|---|---|
| 1 | Auth + API Gateway | FastAPI · MySQL · Redis | 8001 | 8001 |
| 2 | Member Profile | Node/Express · MySQL · Elasticsearch | 8002 | 8002 |
| 3 | Recruiter & Company | Node/Express · MySQL · Redis | 8003 | 8003 |
| 4 | Job Listings | Node/Express · MySQL · Redis | 8004 | 8004 |
| 5 | Applications | Node/Express · MySQL · Redis | 8005 | 8005 |
| 6 | Messaging & Connections | Node/Express · MySQL · MongoDB · Redis | 8006 | 8006 |
| 7 | Analytics + Kafka Host | FastAPI · MongoDB · Redis · Kafka | 8007 | 8007 |
| 8 | AI Agent Orchestrator | FastAPI · MongoDB · Redis | 8008 | 8008 |

---

## Local Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Nikhil-Khaneja/Linkedin_LLM_Agent_Microservices.git
cd Linkedin_LLM_Agent_Microservices

# 2. Start the full stack (builds images on first run)
docker compose -f docker-compose.monorepo.yml up --build -d

# 3. Wait ~60 seconds for all containers to become healthy
docker compose -f docker-compose.monorepo.yml ps

# 4. Verify service health
for port in 8001 8002 8003 8004 8005 8006 8007 8008; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "unreachable"
done

# 5. Seed 500 sample analytics events
python3 scripts/seed_events.py

# 6. Open the frontend
open http://localhost:3000

# 7. Swagger docs
open http://localhost:8001/docs   # Auth
open http://localhost:8007/docs   # Analytics
open http://localhost:8008/docs   # AI
```

### Useful commands

```bash
# Tail logs for one service
docker compose -f docker-compose.monorepo.yml logs -f auth-service

# Rebuild and restart one service after a code change
docker compose -f docker-compose.monorepo.yml build auth-service
docker compose -f docker-compose.monorepo.yml up -d --force-recreate auth-service

# Stop everything and remove volumes (full reset)
docker compose -f docker-compose.monorepo.yml down -v

# Stop without wiping data
docker compose -f docker-compose.monorepo.yml down
```

---

## AWS EC2 — Per-Owner Deployment

Each owner deploys their own service to a separate `t3.micro` EC2 instance (Amazon Linux 2023).

### Step 1 — Provision EC2

1. Launch EC2 instance: Amazon Linux 2023, t3.micro, 20 GB gp3 EBS.
2. Attach a security group (see [Security Group Rules](#security-group-rules) below).
3. Note the public IP — you will share it with the other owners.

### Step 2 — Install Docker on EC2

```bash
ssh -i your-key.pem ec2-user@<your-ec2-ip>

sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
newgrp docker

# Install Docker Compose plugin
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version
```

### Step 3 — Clone and configure

```bash
git clone https://github.com/Nikhil-Khaneja/Linkedin_LLM_Agent_Microservices.git
cd Linkedin_LLM_Agent_Microservices

# Copy and edit the env file with real EC2 IPs once all owners have deployed
cp .env .env.production
nano .env.production
```

### Step 4 — Deploy your service

Each owner runs only their own service container and its direct dependencies (database, Redis).

```bash
# Example: Owner 1 deploys auth-service
docker compose -f docker-compose.monorepo.yml up -d \
  mysql-auth redis auth-service

# Example: Owner 7 deploys analytics + Kafka
docker compose -f docker-compose.monorepo.yml up -d \
  zookeeper kafka mongodb redis analytics-service

# Example: Owner 8 deploys AI service
docker compose -f docker-compose.monorepo.yml up -d \
  mongodb redis ai-service
```

### Step 5 — Update inter-service environment variables

After all owners have launched their EC2 instances and shared their public IPs, update the environment in `docker-compose.monorepo.yml` (or pass as `--env-file`) with real addresses:

```bash
# Re-deploy your service with updated env
docker compose -f docker-compose.monorepo.yml up -d --force-recreate <your-service>
```

---

## Security Group Rules

Open these inbound ports for each owner's EC2. All rules use TCP protocol.

| Owner | Ports to Open | Source | Notes |
|---|---|---|---|
| 1 (Auth) | 8001 | 0.0.0.0/0 | All services need JWKS endpoint |
| 2 (Member) | 8002 | 0.0.0.0/0 | Frontend + service-to-service |
| 3 (Recruiter) | 8003 | 0.0.0.0/0 | |
| 4 (Job) | 8004 | 0.0.0.0/0 | |
| 5 (Application) | 8005 | 0.0.0.0/0 | |
| 6 (Messaging) | 8006 | 0.0.0.0/0 | |
| 7 (Analytics) | 8007 | 0.0.0.0/0 | Analytics API |
| 7 (Kafka) | 29092 | All owner EC2 IPs | Kafka external listener — other owners |
| 8 (AI) | 8008 | 0.0.0.0/0 | |
| All | 3000 | 0.0.0.0/0 | React frontend (if hosting on EC2) |
| All | 22 | Your IP only | SSH access |

**Never expose:** MySQL (3306), MongoDB (27017), Redis (6379), Zookeeper (2181) — bind these to localhost only.

---

## Inter-Service Environment Variables

After all EC2 instances are running, set the following in each service's environment. Replace `<ownerN-ec2-ip>` with the actual public IP.

### All services — connect to Kafka (Owner 7)

```bash
KAFKA_BOOTSTRAP_SERVERS=<owner7-ec2-ip>:29092
```

### Services 2, 4, 5, 8 — validate JWT tokens (Owner 1 JWKS)

```bash
AUTH_JWKS_URL=http://<owner1-ec2-ip>:8001/auth/jwks
```

### AI Service (Owner 8) — call job + application APIs

```bash
JOB_SERVICE_URL=http://<owner4-ec2-ip>:8004
APPLICATION_SERVICE_URL=http://<owner5-ec2-ip>:8005
```

### Frontend — point to all services

```bash
REACT_APP_AUTH_URL=http://<owner1-ec2-ip>:8001
REACT_APP_MEMBER_URL=http://<owner2-ec2-ip>:8002
REACT_APP_RECRUITER_URL=http://<owner3-ec2-ip>:8003
REACT_APP_JOB_URL=http://<owner4-ec2-ip>:8004
REACT_APP_APP_URL=http://<owner5-ec2-ip>:8005
REACT_APP_MESSAGING_URL=http://<owner6-ec2-ip>:8006
REACT_APP_ANALYTICS_URL=http://<owner7-ec2-ip>:8007
REACT_APP_AI_URL=http://<owner8-ec2-ip>:8008
```

---

## Kafka Topic Ownership

| Topic | Published By | Consumed By |
|---|---|---|
| `user.created` | Owner 1 (Auth) | Owner 7 (Analytics) |
| `user.logout` | Owner 1 (Auth) | Owner 7 (Analytics) |
| `member.created` | Owner 2 (Member) | Owner 7 |
| `member.updated` | Owner 2 (Member) | Owner 7 |
| `profile.viewed` | Owner 2 (Member) | Owner 7 |
| `recruiter.created` | Owner 3 (Recruiter) | Owner 7 |
| `recruiter.updated` | Owner 3 (Recruiter) | Owner 7 |
| `job.created` | Owner 4 (Job) | Owner 7, Owner 8 (AI) |
| `job.updated` | Owner 4 (Job) | Owner 7 |
| `job.closed` | Owner 4 (Job) | Owner 7 |
| `job.viewed` | Owner 4 (Job) | Owner 7 |
| `job.search.executed` | Owner 4 (Job) | Owner 7 |
| `application.submitted` | Owner 5 (Application) | Owner 7, Owner 8 |
| `application.status.updated` | Owner 5 (Application) | Owner 7 |
| `application.note.added` | Owner 5 (Application) | Owner 7 |
| `message.sent` | Owner 6 (Messaging) | Owner 7 |
| `thread.opened` | Owner 6 (Messaging) | Owner 7 |
| `connection.requested` | Owner 6 (Messaging) | Owner 7 |
| `connection.accepted` | Owner 6 (Messaging) | Owner 7 |
| `ai.requested` | Owner 8 (AI) | Owner 7 |
| `ai.completed` | Owner 8 (AI) | Owner 7 |
| `ai.approved` | Owner 8 (AI) | Owner 7 |
| `ai.rejected` | Owner 8 (AI) | Owner 7 |
| `analytics.<event_type>` | Owner 7 (Analytics) | Any consumer |
| `benchmark.completed` | Owner 7 (Analytics) | Any consumer |

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Container exits immediately | Missing env var or DB not ready | Check `docker compose logs <service>` — look for connection errors |
| `host not found in upstream` in nginx | Proxy block references a hostname not on the Docker network | Remove or update the `upstream` block in `nginx.conf` |
| Auth service 500 on `/auth/register` | `refresh_tokens` table schema mismatch | Run `docker exec linkedin-mysql-auth mysql -u auth_user -pauth_pass auth_access -e "DESCRIBE refresh_tokens;"` and verify columns match the model |
| Kafka `IllegalArgumentException: Each listener must have a unique port` | Two listeners mapped to the same port in `KAFKA_LISTENERS` | Ensure `PLAINTEXT` and `PLAINTEXT_HOST` use different port numbers |
| Port already allocated on host | Another container from a different compose project holds the host port | Change the host port (left side of `host:container`) in `docker-compose.monorepo.yml` |
| Node service can't connect to Redis | Service reads `REDIS_URL` but compose sets `REDIS_HOST`/`REDIS_PORT` | Use `REDIS_URL: redis://redis:6379` in the compose env block |
| Node service can't connect to MySQL | Service reads `MYSQL_HOST` but compose sets `DB_HOST` | Rename env var to match what the service code expects |
| Member service: `Table 'member_core.members' doesn't exist` | No schema SQL mounted into the MySQL container | Mount `schema.sql` via `docker-entrypoint-initdb.d` volume in the MySQL service definition |
| `bcrypt` error: `module has no attribute '__about__'` | `passlib` is incompatible with `bcrypt >= 5.0` | Pin `bcrypt==4.1.3` in `requirements.txt` |
| `ImportError: cannot import name 'X'` | Typo in filename or wrong import path | Check the actual filename on disk vs the import string |
| Elasticsearch container unhealthy | Needs `vm.max_map_count` raised on Linux hosts | Run `sudo sysctl -w vm.max_map_count=262144` on the EC2 host |
| JWT validation fails on other services | `AUTH_JWKS_URL` points to wrong host/port | Set `AUTH_JWKS_URL=http://<owner1-ec2-ip>:8001/auth/jwks` |
| Kafka consumer never receives messages | Wrong `KAFKA_BOOTSTRAP_SERVERS` | Verify it points to Owner 7's EC2 external listener: `<owner7-ip>:29092` |
