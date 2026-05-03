# LinkedIn Simulation — Distributed Systems Class Project

Full-stack LinkedIn clone built as a distributed systems course project. Eight FastAPI microservices, React frontend, Kafka-first async flows, Redis caching, MySQL + MongoDB persistence, AI Career Coach, and JMeter performance benchmarks.

---

## Team

| Person | Name | Responsibilities |
|--------|------|-----------------|
| Person 1 | Nikhil Khaneja | Kafka-first flows, auth/infra, exception handling, notifications, AWS Terraform |
| Person 2 | Shreya | AI Career Coach, AI evaluation metrics, outreach drafts |
| Person 3 | Drashti | Salary filter, FULLTEXT job search, low-traction chart, 10k dataset loader |
| Person 4 | Sanjay | JMeter benchmarks, ECS task definitions, performance analysis |

---

## Architecture

```
React Frontend (5173)
        │
        ▼
┌──────────────────────────────────────────────────────┐
│  FastAPI Services                                    │
│  auth (8001) · member (8002) · recruiter (8003)     │
│  jobs (8004) · applications (8005)                  │
│  messaging (8006) · analytics (8007) · AI (8008)    │
└──────────┬───────────────┬──────────────────────────┘
           │               │
        Kafka           Redis
      (async)          (cache)
           │
    ┌──────┴──────┐
  MySQL        MongoDB
(relational)  (documents)
```

**Kafka-first write path (Person 1):**
`POST /applications/submit` → publishes `application.submit.requested` → Kafka consumer writes to MySQL → publishes `application.submitted` → returns HTTP 202

---

## What's Implemented

### Core Services
| Service | Port | Key Endpoints |
|---------|------|---------------|
| auth_service | 8001 | /auth/register, /auth/login, /auth/refresh, /auth/logout |
| member_profile_service | 8002 | /members/create, get, update, search |
| recruiter_company_service | 8003 | /recruiters/create, get, update; /companies/create |
| jobs_service | 8004 | /jobs/create, get, update, close, search, byRecruiter, save |
| applications_service | 8005 | /applications/submit (202 async), get, byJob, byMember, updateStatus |
| messaging_connections_service | 8006 | /threads/open, /messages/send, /connections/request, accept, reject |
| analytics_service | 8007 | /analytics/jobs/top, funnel, geo, member/dashboard, /benchmarks/report |
| ai_orchestrator_service | 8008 | /ai/tasks/create, approve, reject; /ai/coach/suggest; /ai/analytics/approval-rate |

### Frontend Pages
- **Jobs** — search, salary filter, save, apply (Kafka-first async)
- **Job Detail** — resume upload/paste + apply
- **Member Profile** — edit skills, headline, resume
- **Applications** — status tracking (submitted → reviewing → interview → offer/rejected)
- **Messaging** — threads + real-time send
- **Connections** — request, accept, withdraw
- **Notifications** — live badge count (polls every 10s), mark-as-read
- **Recruiter Dashboard** — post/edit/close jobs, view applicants, update status, 5 analytics charts
- **AI Dashboard** — shortlist candidates, approve/edit/reject outreach drafts
- **Career Coach** — match score, suggested headline, skills to add, resume tips (OpenRouter LLM)
- **Analytics** — recruiter metrics, member activity, performance benchmarks tab

### Key Features
- **Kafka-first submit** — application submit is fully async; HTTP 202 returned immediately
- **Salary filter** — `salary_min` / `salary_max` columns + search filter (Person 3)
- **FULLTEXT search** — MySQL FULLTEXT index on `jobs(title, location_text)` (Person 3)
- **AI Career Coach** — `POST /ai/coach/suggest` scores your profile vs. job, suggests improvements (Person 2)
- **Application funnel** — Viewed → Saved → Started → Submitted per job (dropdown selector)
- **Geo chart** — city-wise applications per job (dropdown selector)
- **Edit job** — inline edit form on Recruiter Dashboard
- **Performance benchmarks** — 4 configs (B, B+S, B+S+K, B+S+K+Other) with live charts
- **Exception handling** — duplicate email 409, duplicate application 409, closed job 409, DLQ
- **Idempotency** — all write endpoints accept `Idempotency-Key` header
- **RS256 JWT** — auth_service issues; all services validate offline via JWKS

---

## Quick Start (Local)

### 1. Clone & configure

```bash
git clone https://github.com/Nikhil-Khaneja/Linkedin_Prototype_LLM_Agent_Microservices.git
cd Linkedin_Prototype_LLM_Agent_Microservices
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY for AI Coach (optional but recommended)
```

### 2. Start all services

```bash
docker compose up -d
# Wait ~60s for all health checks
docker compose ps   # all 17 should show healthy/Up
```

### 3. Apply schema & seed data

```bash
bash scripts/bootstrap_local.sh          # migrations + Kafka topics
/opt/homebrew/bin/python3 scripts/seed_demo_data.py   # creates demo accounts + seed jobs
/opt/homebrew/bin/python3 scripts/load_kaggle_datasets.py --synthetic  # loads 10k jobs + 5k members
```

### 4. Open the app

| URL | What |
|-----|------|
| http://localhost:5173 | Frontend |
| http://localhost:3000 | Grafana (admin/admin) |
| http://localhost:9000 | MinIO (minioadmin/minioadmin) |
| http://localhost:8001/docs | Auth service Swagger |

---

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Member | ava@example.com | StrongPass#1 |
| Recruiter | recruiter@example.com | RecruiterPass#1 |

---

## Performance Benchmarks (Person 4)

```bash
# Run all 4 configs (requires full stack running):
/opt/homebrew/bin/python3 scripts/run_performance_benchmarks.py --all

# Or individual config:
/opt/homebrew/bin/python3 scripts/run_performance_benchmarks.py --config "B+S+K"
```

Results stored in analytics_service → visible in **Analytics → Performance & benchmarks** tab.

| Config | Description |
|--------|-------------|
| B | Baseline — no Redis, no Kafka |
| B+S | Base + Redis cache |
| B+S+K | Base + Redis + Kafka (default stack) |
| B+S+K+Other | Base + Redis + Kafka + scaled replicas |

---

## Ops Endpoints

Every service exposes:
```
GET /ops/healthz      → {"status": "ok", "service": "...", "version": "..."}
GET /ops/cache-stats  → {"lookups": n, "hits": n, "misses": n, "hit_rate": 0.xx}
GET /ops/metrics      → Prometheus text format
```

---

## Tests

```bash
# Compile check:
python3 -m compileall backend

# API smoke tests:
/opt/homebrew/bin/python3 -m pytest tests/api -q -p no:deepeval
```

---

## Project Structure

```
├── backend/
│   └── services/
│       ├── shared/              # JWT, Kafka bus, Redis cache, repositories
│       ├── auth_service/
│       ├── member_profile_service/
│       ├── recruiter_company_service/
│       ├── jobs_service/
│       ├── applications_service/
│       ├── messaging_connections_service/
│       ├── analytics_service/
│       └── ai_orchestrator_service/
├── frontend/
│   └── src/pages/               # React pages (Jobs, Profile, Coach, Analytics, …)
├── infra/
│   ├── mysql/                   # 001–006 migration files
│   └── mongo/                   # MongoDB init
├── deploy/
│   └── aws_accounts/            # Per-owner docker-compose.aws.yml + ECS task defs
├── infra/aws/                   # Terraform (VPC, ALB, ECS, RDS, ElastiCache, ECR)
├── scripts/                     # bootstrap, seed, load_kaggle_datasets, benchmarks
├── tests/
│   ├── api/                     # pytest smoke tests
│   └── jmeter/                  # scenario_a.jmx, scenario_b.jmx
├── observability/               # Prometheus, Grafana, Promtail config
└── docs/
    ├── LOCAL_SETUP_RUNBOOK.md   # Step-by-step local setup guide
    ├── PERFORMANCE_ANALYSIS.md  # Benchmark results write-up
    ├── architecture.md
    └── aws_deploy_step_by_step.md
```

---

## AWS Deployment

Terraform infrastructure in `infra/aws/`:
- VPC + subnets + security groups
- ALB with path-based routing
- ECS Fargate (8 backend services + frontend)
- RDS MySQL, ElastiCache Redis, DocumentDB, ECR

Per-owner EC2 deployment configs in `deploy/aws_accounts/` (owner1–owner9).

```bash
cd infra/aws
terraform init && terraform apply
bash push_images.sh    # build + push ECR images
bash deploy.sh         # register task defs + update ECS services
```

---

## Local Setup Runbook

See `docs/LOCAL_SETUP_RUNBOOK.md` for the complete step-by-step guide to reproduce the full local stack from scratch.
