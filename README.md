# LinkedIn Simulation — Distributed Microservices Platform

> 8-owner distributed system simulating LinkedIn's core functionality with agentic AI, event-driven architecture, and AWS multi-account deployment.

---

## Overview

This monorepo contains all 8 microservices built collaboratively across 8 owners. Each service is independently deployable on its own EC2 instance, communicates over Kafka (hosted by Owner 7), and exposes a REST API consumed by the shared React frontend.

| Owner | Service | Tech Stack | Port |
|---|---|---|---|
| Owner 1 | Auth + API Gateway | FastAPI · MySQL · Redis · RS256 JWT | 8001 |
| Owner 2 | Member Profile | Node/Express · MySQL · Elasticsearch | 8002 |
| Owner 3 | Recruiter & Company | Node/Express · MySQL · Redis | 8003 |
| Owner 4 | Job Listings | Node/Express · MySQL · Redis | 8004 |
| Owner 5 | Applications | Node/Express · MySQL · Redis | 8005 |
| Owner 6 | Messaging & Connections | Node/Express · MongoDB · Redis | 8006 |
| Owner 7 | Analytics + Kafka Host | FastAPI · MongoDB · Redis · Kafka | 8007 |
| Owner 8 | AI Agent Orchestrator | FastAPI · MongoDB · Redis | 8008 |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        React Frontend (nginx)                        │
│                   Calls each service directly by port                │
└───┬────────┬────────┬────────┬────────┬────────┬────────┬───────────┘
    │        │        │        │        │        │        │
  :8001    :8002    :8003    :8004    :8005    :8006    :8007   :8008
  Auth    Member  Recruiter  Job     Apply   Message  Analytics  AI
    │        │        │        │        │        │        │
    └────────┴────────┴────────┴───────►│        │        │
                                        ▼        ▼        ▼
                                       Kafka Broker (Owner 7 EC2)
                                       Topics: user.*, job.*, application.*
                                                member.*, message.*, ai.*
```

**Auth flow:** Owner 1 issues RS256 JWTs. All other services validate tokens via the JWKS endpoint at `http://auth-service:8001/auth/jwks`.

**Event flow:** Every service publishes domain events to Kafka. Owner 7 consumes all 23 topics for analytics aggregation. Owner 8 consumes job/application events to trigger AI recommendations.

---

## Local Quick Start (Full Stack)

```bash
# Clone the repo
git clone https://github.com/Nikhil-Khaneja/Linkedin_LLM_Agent_Microservices.git
cd Linkedin_LLM_Agent_Microservices

# Start all 8 services + infrastructure
docker compose -f docker-compose.monorepo.yml up -d

# Wait ~60s for all health checks to pass, then verify
docker compose -f docker-compose.monorepo.yml ps

# Seed analytics sample data (30 days of synthetic events)
python3 scripts/seed_events.py

# Frontend
open http://localhost:3000

# Swagger docs per service
open http://localhost:8001/docs   # Auth
open http://localhost:8007/docs   # Analytics
open http://localhost:8008/docs   # AI
```

---

## Services

### Owner 1 — Auth Service (`services/auth-service`)

FastAPI service handling registration, login, token refresh, and logout. Issues RS256 JWTs. Exposes a JWKS endpoint used by all other services for token validation.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register new user, returns access + refresh tokens |
| POST | `/auth/login` | Login, returns access + refresh tokens |
| POST | `/auth/refresh` | Rotate refresh token |
| POST | `/auth/logout` | Revoke refresh token |
| GET | `/auth/jwks` | RS256 public key in JWKS format |
| GET | `/health` | Health check |

**Stack:** FastAPI · SQLAlchemy · PyMySQL · passlib/bcrypt · python-jose RS256 · Redis (rate limiting) · Alembic

---

### Owner 2 — Member Profile Service (`services/member-service`)

Node/Express service for member profiles with full-text search via Elasticsearch.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| POST | `/members` | Create member profile |
| GET | `/members/:id` | Get member by ID |
| PUT | `/members/:id` | Update profile |
| GET | `/members/search?q=` | Full-text search via Elasticsearch |
| GET | `/health` | Health check |

**Stack:** Node.js · Express · MySQL · Elasticsearch · ioredis

---

### Owner 3 — Recruiter & Company Service (`services/recruiter-service`)

Node/Express service managing recruiter accounts and company profiles.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| POST | `/recruiters` | Create recruiter |
| GET | `/recruiters/:id` | Get recruiter |
| POST | `/companies` | Create company |
| GET | `/companies/:id` | Get company |
| GET | `/health` | Health check |

**Stack:** Node.js · Express · MySQL · ioredis

---

### Owner 4 — Job Service (`services/job-service`)

Node/Express service for job postings with Redis-cached search.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/jobs` | Create job posting |
| GET | `/api/v1/jobs/:id` | Get job by ID |
| GET | `/api/v1/jobs/search` | Search jobs (Redis-cached) |
| PUT | `/api/v1/jobs/:id` | Update job |
| DELETE | `/api/v1/jobs/:id` | Close job |
| GET | `/health` | Health check |

**Stack:** Node.js · Express · MySQL · Redis · KafkaJS

---

### Owner 5 — Application Service (`services/application-service`)

Node/Express service tracking job applications through their lifecycle.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| POST | `/applications` | Submit application |
| GET | `/applications/:id` | Get application |
| PUT | `/applications/:id/status` | Update status |
| GET | `/applications/member/:memberId` | All applications by member |
| GET | `/health` | Health check |

**Stack:** Node.js · Express · MySQL · Redis · KafkaJS

---

### Owner 6 — Messaging & Connections Service (`services/messaging-service`)

Node/Express service for direct messages and connection requests.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| POST | `/messages` | Send message |
| GET | `/messages/thread/:threadId` | Get message thread |
| POST | `/connections/request` | Send connection request |
| PUT | `/connections/:id/accept` | Accept connection |
| GET | `/health` | Health check |

**Stack:** Node.js · Express · MongoDB · ioredis · KafkaJS

---

### Owner 7 — Analytics Service (`services/analytics-service`)

FastAPI service that consumes all Kafka events and provides analytics dashboards, funnel analysis, geo distribution, and benchmark reporting. Also hosts the shared Kafka broker for all other owners.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| POST | `/events/ingest` | Ingest event (idempotent) |
| POST | `/analytics/jobs/top` | Top jobs by metric |
| POST | `/analytics/funnel` | View→Save→Apply funnel |
| POST | `/analytics/geo` | Geo distribution of activity |
| POST | `/analytics/member/dashboard` | Member engagement rollup |
| POST | `/benchmarks/report` | Store JMeter benchmark result |
| GET | `/health` | Health check |

**Stack:** FastAPI · Motor (MongoDB async) · Redis · aiokafka · Pydantic v2

---

### Owner 8 — AI Agent Orchestrator (`services/ai-service`)

FastAPI service that uses LLM-based agents to match members with jobs, generate application recommendations, and process AI approval workflows.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| POST | `/ai/recommend` | Generate job recommendations for member |
| POST | `/ai/approve` | Human-in-the-loop approval step |
| GET | `/ai/status/:requestId` | Check AI request status |
| GET | `/health` | Health check |

**Stack:** FastAPI · Motor (MongoDB) · Redis · aiokafka · LangChain / OpenAI

---

## Infrastructure

### Kafka Event Bus

Owner 7's EC2 hosts the shared Kafka broker. All services connect to it for event publishing and consumption.

**Standard event envelope** (all owners must follow this schema):

```json
{
  "event_type": "application.submitted",
  "trace_id": "trc_7744",
  "timestamp": "2026-04-02T20:00:00Z",
  "actor_id": "mem_501",
  "entity": {
    "entity_type": "application",
    "entity_id": "app_8807"
  },
  "payload": {},
  "idempotency_key": "mem501-job3301-v1"
}
```

**Topics by domain:**

| Domain | Topics |
|---|---|
| Auth | `user.created`, `user.logout` |
| Member | `member.created`, `member.updated`, `profile.viewed` |
| Recruiter | `recruiter.created`, `recruiter.updated` |
| Job | `job.created`, `job.updated`, `job.closed`, `job.viewed`, `job.search.executed` |
| Application | `application.submitted`, `application.status.updated`, `application.note.added` |
| Messaging | `message.sent`, `thread.opened`, `connection.requested`, `connection.accepted` |
| AI | `ai.requested`, `ai.completed`, `ai.approved`, `ai.rejected` |
| Analytics | `analytics.<event_type>`, `benchmark.completed` |

### Databases

Each service owns its own database — no cross-service DB access.

| Service | Database | Container |
|---|---|---|
| auth-service | MySQL `auth_access` | `mysql-auth:3306` |
| member-service | MySQL `member_core` | `mysql-member:3306` |
| recruiter-service | MySQL `recruiter_core` | `mysql-recruiter:3306` |
| job-service | MySQL `job_core` | `mysql-job:3306` |
| application-service | MySQL `application_core` | `mysql-app:3306` |
| messaging-service | MongoDB | `mongodb:27017` |
| analytics-service | MongoDB `analytics` | `mongodb:27017` |
| ai-service | MongoDB `ai_service` | `mongodb:27017` |

### Shared Infrastructure

| Service | Purpose |
|---|---|
| Redis | Rate limiting (auth), query caching (analytics, job, application) |
| Kafka + Zookeeper | Event bus for all inter-service communication |
| Elasticsearch | Full-text member profile search (member-service) |

---

## Monorepo Structure

```
.
├── services/
│   ├── auth-service/          # Owner 1 — FastAPI, RS256 JWT
│   ├── member-service/        # Owner 2 — Node/Express, Elasticsearch
│   ├── recruiter-service/     # Owner 3 — Node/Express
│   ├── job-service/           # Owner 4 — Node/Express, Redis cache
│   ├── application-service/   # Owner 5 — Node/Express
│   ├── messaging-service/     # Owner 6 — Node/Express, MongoDB
│   ├── analytics-service/     # Owner 7 — FastAPI, MongoDB, Kafka host
│   └── ai-service/            # Owner 8 — FastAPI, LLM agents
├── frontend/                  # React SPA (connects to all 8 services)
├── shared/
│   └── kafka_utils.py         # Shared async Kafka producer/consumer utility
├── k8s/                       # Kubernetes manifests (k3s on EC2)
├── scripts/
│   ├── build-push.sh          # Build + push all Docker images
│   ├── deploy.sh              # Apply k8s manifests
│   ├── ec2-setup.sh           # Bootstrap EC2 with k3s
│   ├── ec2-deploy-service.sh  # Deploy individual service to EC2
│   ├── ec2-kafka-setup.sh     # Setup shared Kafka on Owner 7 EC2
│   ├── api-gateway-nginx.conf # Nginx reverse proxy config for EC2
│   └── seed_events.py         # Seed 30 days of synthetic analytics data
├── jmeter/                    # JMeter benchmark plans (Scenario A + B)
├── tests/                     # Owner 7 unit + API integration tests
├── docker-compose.monorepo.yml  # Full stack local development
└── .github/workflows/         # CI/CD per owner
```

---

## Docker Compose — Full Stack

```bash
# Start everything
docker compose -f docker-compose.monorepo.yml up -d

# View logs for a specific service
docker compose -f docker-compose.monorepo.yml logs -f auth-service

# Rebuild a single service after code changes
docker compose -f docker-compose.monorepo.yml build auth-service
docker compose -f docker-compose.monorepo.yml up -d --force-recreate auth-service

# Stop everything
docker compose -f docker-compose.monorepo.yml down
```

**Service health check URLs:**

```
http://localhost:8001/health   # auth
http://localhost:8002/health   # member
http://localhost:8003/health   # recruiter
http://localhost:8004/health   # job
http://localhost:8005/health   # application
http://localhost:8006/health   # messaging
http://localhost:8007/health   # analytics
http://localhost:8008/health   # ai
```

---

## AWS Deployment

Each owner deploys their service to their own EC2 instance. Owner 7 additionally hosts the shared Kafka broker.

### Per-Service Deployment

```bash
# Build and push Docker images
./scripts/build-push.sh <dockerhub-username>

# Deploy a service to its EC2 instance
./scripts/ec2-deploy-service.sh <ec2-ip> <service-name> <dockerhub-username>

# Setup shared Kafka on Owner 7 EC2
./scripts/ec2-kafka-setup.sh <owner7-ec2-ip>
```

### Kubernetes (k3s) Deployment

```bash
# Bootstrap EC2 with k3s
./scripts/ec2-setup.sh <ec2-ip>

# Deploy all k8s manifests
./scripts/deploy.sh <dockerhub-username>
```

### Security Group Rules

| Port | Open To | Purpose |
|---|---|---|
| 8001–8008 | All owner EC2s + public | Service APIs |
| 9092 | All owner EC2s | Kafka internal |
| 29092 | All owner EC2s | Kafka external (Owner 7 only) |
| 3000 | Public | React frontend |
| 27017, 6379 | localhost only | MongoDB, Redis (never expose) |

---

## CI/CD

GitHub Actions workflows in `.github/workflows/` handle build, test, and deploy per owner branch.

```yaml
# Trigger: push to owner branch
# Steps: build Docker image → push to DockerHub → SSH deploy to EC2
```

Each owner has their own workflow file (e.g., `deploy-analytics-service.yml` for Owner 7).

---

## Performance Benchmarks

JMeter load tests run against the full stack via Docker:

```bash
# Run both benchmark scenarios
docker compose -f docker-compose.monorepo.yml --profile benchmark run --rm jmeter

# Scenario A — ingest stress test
docker compose -f docker-compose.monorepo.yml --profile benchmark run --rm -e SCENARIO=A jmeter

# Scenario B — analytics query load test
docker compose -f docker-compose.monorepo.yml --profile benchmark run --rm -e SCENARIO=B jmeter
```

| Scenario | Endpoint | Threads | Requests | Throughput | Avg Latency | Error Rate |
|---|---|---|---|---|---|---|
| A — Ingest | `POST /events/ingest` | 50 | 10,000 | **186 req/s** | 3ms | 0% |
| B — Queries | Analytics endpoints | 30 | 12,000 | **117 req/s** | 2ms | 0% |

---

## Jira Tickets

| Ticket | Owner | Summary |
|---|---|---|
| LI-01 | Owner 1 | Auth service — JWT, register, login, JWKS |
| LI-02 | Owner 2 | Member profile — CRUD, Elasticsearch search |
| LI-03 | Owner 3 | Recruiter + company management |
| LI-04 | Owner 4 | Job listings — CRUD, Redis-cached search |
| LI-05 | Owner 5 | Application lifecycle — submit, status updates |
| LI-06 | Owner 6 | Messaging + connection graph |
| LI-07 | Owner 7 | Analytics hub — event ingest, dashboards, Kafka host |
| LI-08 | Owner 8 | AI agent orchestrator — LLM recommendations, approval flow |
| LI-15 | Owner 7 | Kafka event envelope standard + cross-service integration |
| LI-23 | Owner 7 | Dashboard rollups from Kafka streams |
| LI-31 | Owner 7 | Benchmark report generation + presentation artifacts |
