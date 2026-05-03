# Local Setup Runbook
# LinkedIn Simulation — Full Stack (All 4 Persons Integrated)

**Last verified:** 2026-05-03  
**Branch state:** main (all persons merged)

---

## Prerequisites

- Docker Desktop running (≥ 4 GB RAM allocated)
- `/opt/homebrew/bin/python3` (Python 3.10+) for scripts
- JMeter at `/opt/homebrew/bin/jmeter` for benchmarks
- Git

---

## 1. Clone & Environment

```bash
git clone https://github.com/Nikhil-Khaneja/Linkedin_Prototype_LLM_Agent_Microservices.git
cd Linkedin_Prototype_LLM_Agent_Microservices

cp .env.example .env
# Edit .env and set:
#   OPENROUTER_API_KEY=<your key>   ← required for AI Coach (OpenRouter)
#   SECRET_KEY=<any long string>    ← JWT signing key
#   All other defaults are fine for local
```

---

## 2. Start the Full Stack

```bash
docker compose up -d
```

Wait ~60 seconds for all health checks to pass:

```bash
docker compose ps
# All 17 services should show "healthy" or "Up"
```

**Services & Ports:**
| Service | Port |
|---|---|
| frontend (React dev) | 5173 |
| auth_service | 8001 |
| member_profile_service | 8002 |
| recruiter_company_service | 8003 |
| jobs_service | 8004 |
| applications_service | 8005 |
| messaging_connections_service | 8006 |
| analytics_service | 8007 |
| ai_orchestrator_service | 8008 |
| MySQL | 3306 |
| MongoDB | 27017 |
| Redis | 6379 |
| Kafka (KRaft) | 9092 |
| MinIO | 9000 |
| Grafana | 3000 |

---

## 3. Apply Database Migrations

Run once after first start (or after a fresh DB volume):

```bash
# MySQL migrations (run in order)
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/001_init.sql
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/002_indexes.sql
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/002_member_profile_resume.sql
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/003_constraints_and_views.sql
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/003_member_structured_profile.sql
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/004_expand_media_columns.sql
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/004_saved_jobs.sql
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/005_salary_range.sql
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim < /dev/stdin" < infra/mysql/006_jobs_fulltext.sql

# Or use the helper script:
bash scripts/apply_mysql_schema.sh

# MongoDB init
bash scripts/apply_mongo_init.sh
```

Or use the bootstrap script (does migrations + Kafka topics + seeds):

```bash
bash scripts/bootstrap_local.sh
```

---

## 4. Create Kafka Topics

```bash
bash scripts/create_kafka_topics.sh
```

---

## 5. Seed Demo Data

### 5a. Core demo accounts (ava + recruiter + seed jobs)

```bash
/opt/homebrew/bin/python3 scripts/seed_demo_data.py
```

This creates:
- **Member:** `ava@example.com` / `StrongPass#1`  
- **Recruiter:** `recruiter@example.com` / `RecruiterPass#1`
- Seed jobs, applications, connections

### 5b. Load 10k synthetic dataset (Person 3 — Drashti)

```bash
/opt/homebrew/bin/python3 scripts/load_kaggle_datasets.py --synthetic
```

This loads:
- 10,000 synthetic jobs with salary ranges
- 5,000 synthetic members
- Uses `INSERT IGNORE` — safe to re-run

**Verify:**
```bash
docker exec project-mysql-1 bash -c "mysql -u root -proot linkedin_sim -e 'SELECT COUNT(*) FROM jobs; SELECT COUNT(*) FROM members;'" 2>/dev/null
# Expected: ~10,204 jobs, ~5,204 members
```

---

## 6. Rebuild Specific Services (after code changes)

```bash
# After changing any backend service:
docker compose build <service_name> && docker compose up -d --no-deps <service_name>

# Services:
#   auth_service, member_profile_service, recruiter_company_service
#   jobs_service, applications_service, messaging_connections_service
#   analytics_service, ai_orchestrator_service

# Frontend reloads automatically (volume-mounted dev server)
# If package.json changed:
docker exec project-frontend-1 bash -c "cd /web && npm install"
```

---

## 7. Demo Accounts & Credentials

| Role | Email | Password | ID |
|---|---|---|---|
| Member | ava@example.com | StrongPass#1 | mem_501 |
| Recruiter | recruiter@example.com | RecruiterPass#1 | rec_120 |

---

## 8. Run Performance Benchmarks (Person 4 — Sanjay)

```bash
# Full stack (Redis + Kafka) — recommended:
/opt/homebrew/bin/python3 scripts/run_performance_benchmarks.py --config "B+S+K"

# All 4 configs in sequence:
/opt/homebrew/bin/python3 scripts/run_performance_benchmarks.py --all

# Baseline (no Redis/Kafka) — requires override file:
docker compose -f docker-compose.yml -f docker-compose.override.baseline.yml up -d
/opt/homebrew/bin/python3 scripts/run_performance_benchmarks.py --config "B"
# Restore full stack after:
docker compose up -d
```

Results are stored in analytics_service and visible at:  
`http://localhost:5173` → Analytics → **Performance & benchmarks** tab

---

## 9. AI Coach (Person 2 — Shreya)

Requires `OPENROUTER_API_KEY` set in `.env`.

After setting the key, restart AI service:
```bash
docker compose up -d --no-deps ai_orchestrator_service
```

Test via frontend: `http://localhost:5173/coach` (login as member)

---

## 10. Key URLs

| URL | What |
|---|---|
| http://localhost:5173 | Frontend (React) |
| http://localhost:3000 | Grafana (admin/admin) |
| http://localhost:9000 | MinIO (minioadmin/minioadmin) |
| http://localhost:8001/docs | Auth service Swagger |
| http://localhost:8007/docs | Analytics service Swagger |

---

## 11. Teardown & Reset

```bash
# Stop all containers (keep volumes/data):
docker compose down

# Full reset (DELETE all data):
docker compose down -v

# Restart fresh:
docker compose up -d
# Then re-run steps 3–5 to restore data
```

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| Service shows "unhealthy" | `docker compose logs <service>` to see error |
| 401 on all requests | Token expired (15 min TTL) — log in again |
| AI Coach returns "heuristic" | `OPENROUTER_API_KEY` not set or service not restarted after setting |
| Jobs not showing for member | "Hide applied" checkbox is ON by default — uncheck it |
| Recruiter jobs missing | Jobs may belong to different recruiter_id — check DB |
| Kafka consumer not processing | Check `EVENT_BUS_MODE` is not `memory` in .env |
| Port already allocated on scale | Fixed port bindings prevent `--scale` locally; run single instance |
