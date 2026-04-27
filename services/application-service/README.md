# Owner 5 — Application Service
**LinkedIn Simulation + Agentic AI Services — Distributed Systems Class Project**

---

## What This Service Does

Owner 5 is the **Application Service** for the LinkedIn simulation. It handles everything related to job applications:

- Members submit job applications
- Duplicate applications are blocked (Redis fast-check + MySQL constraint)
- Applying to closed jobs is rejected
- Recruiters update application status and add notes
- Kafka events are published for every mutation
- Job lifecycle events from Owner 4 are consumed to keep a local job status projection

---

## Owner 5 Responsibilities

| # | Responsibility |
|---|----------------|
| 1 | Submit job application |
| 2 | Prevent duplicate applications (Redis + MySQL UNIQUE) |
| 3 | Block applying to closed jobs (local job_status_projection table) |
| 4 | Get application details |
| 5 | List applications by job (recruiter view) |
| 6 | List applications by member (member view) |
| 7 | Recruiter updates application status |
| 8 | Recruiter adds notes to application |
| 9 | Publish Kafka events: `application.submitted`, `application.status.updated`, `application.note.added` |
| 10 | Consume Kafka events: `job.created`, `job.updated`, `job.closed` |
| 11 | Maintain local `job_status_projection` table |
| 12 | Provide Docker Compose (API + MySQL + Redis) |
| 13 | Seed data for standalone testing |
| 14 | Tests with pytest |
| 15 | Scenario B benchmark with k6 |

---

## Standalone Mode vs Integration Mode

| Setting | Standalone Demo Mode | Team Integration Mode |
|---------|---------------------|----------------------|
| `DEMO_ALLOW_UNKNOWN_JOB` | `true` | `false` |
| MySQL | Local Docker Compose | Owner 5 EC2 MySQL |
| Redis | Local Docker Compose | Owner 5 EC2 Redis |
| Kafka | Unavailable — API still works | Owner 7 EC2 Kafka broker |
| Job status | Seeded from `seed.sql` | Consumed from Owner 4 Kafka events |

---

## Architecture Summary

```
Member/Recruiter (HTTP)
        │
        ▼
 FastAPI (port 8005)
        │
   ┌────┴────────────────┐
   │                     │
   ▼                     ▼
MySQL (application_core) Redis (idempotency keys)
   │
   ▼
Kafka Producer ──► application.submitted
                   application.status.updated
                   application.note.added

Owner 4 Kafka ──► job.created / job.updated / job.closed
                        │
                        ▼
               job_status_projection (MySQL)
```

---

## API Endpoints

| Method | Path | Description | Kafka event |
|--------|------|-------------|-------------|
| GET | `/health` | Health check | — |
| POST | `/applications/submit` | Submit application | `application.submitted` |
| POST | `/applications/get` | Get application detail | — |
| POST | `/applications/byJob` | List by job (recruiter) | — |
| POST | `/applications/byMember` | List by member | — |
| POST | `/applications/updateStatus` | Update lifecycle status | `application.status.updated` |
| POST | `/applications/addNote` | Add recruiter note | `application.note.added` |

**Swagger UI:** `http://localhost:8005/docs`

> **Authentication:** All `/applications/*` endpoints require a Bearer token.
> Include the header `Authorization: Bearer owner5-demo-token` (or your configured `API_BEARER_TOKEN`) in every request.
> The `/health` endpoint is public and requires no token.

---

## Database Tables

**Database:** `application_core` (MySQL)

| Table | Purpose |
|-------|---------|
| `applications` | Core application records; UNIQUE(job_id, member_id) |
| `application_answers` | Per-application question answers |
| `recruiter_notes` | Recruiter notes on applications |
| `job_status_projection` | Local copy of Owner 4 job status (open/closed) |
| `consumed_kafka_events` | Idempotency tracking for Kafka consumer |

---

## Redis Duplicate Prevention

**Key format:** `apply:idem:{member_id}:{job_id}`  
**TTL:** 86400 seconds (24 hours, configurable)

**Flow:**
1. On `POST /applications/submit`, Redis key is checked first (fast path).
2. If key exists → return **HTTP 409** immediately.
3. If not → set the key, then write to MySQL.
4. MySQL `UNIQUE(job_id, member_id)` is the **final safety guarantee**.
5. Redis is the fast guard to reduce DB load.
6. If Redis is unavailable, the MySQL constraint still protects correctness.

---

## Kafka Events Produced

**Envelope format:**
```json
{
  "event_type": "application.submitted",
  "event_id":   "evt_abc123",
  "trace_id":   "trc_xyz789",
  "timestamp":  "2026-04-24T10:00:00Z",
  "actor_id":   "mem_501",
  "entity": {
    "entity_type": "application",
    "entity_id":   "app_abc123"
  },
  "payload": {
    "job_id":     "job_3301",
    "member_id":  "mem_501",
    "resume_ref": "s3://bucket/resume-501.pdf"
  },
  "idempotency_key": "mem501-job3301-v1"
}
```

| Topic | Trigger |
|-------|---------|
| `application.submitted` | Successful application insert |
| `application.status.updated` | Recruiter updates status |
| `application.note.added` | Recruiter adds note |

> **Kafka failure never crashes the API** after a successful DB commit. Failures are logged.

---

## Kafka Events Consumed

From Owner 4 (`job.created`, `job.updated`, `job.closed`):

```json
{
  "event_type": "job.closed",
  "event_id":   "evt_job001",
  "entity":     { "entity_type": "job", "entity_id": "job_3301" },
  "payload":    { "job_id": "job_3301", "recruiter_id": "rec_120", "status": "closed" }
}
```

The consumer upserts `job_status_projection` and marks the event in `consumed_kafka_events` (idempotent).

---

## Environment Variables

| Variable | Default (Docker) | Description |
|----------|-----------------|-------------|
| `API_BEARER_TOKEN` | `owner5-demo-token` | Bearer token required on all `/applications/*` endpoints |
| `DB_HOST` | `mysql` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_NAME` | `application_core` | MySQL database |
| `DB_USER` | `app_user` | MySQL user |
| `DB_PASSWORD` | `app_password` | MySQL password |
| `REDIS_HOST` | `redis` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_IDEMPOTENCY_TTL_SECONDS` | `86400` | Redis key TTL |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Owner 7 Kafka broker |
| `DEMO_ALLOW_UNKNOWN_JOB` | `true` | Allow unknown job IDs in demo mode |

Copy `.env.example` to `.env` and edit as needed.

---

## How to Run with Docker Compose

```bash
# 1. Clone / navigate to the service
cd owner5-application-service

# 2. Copy env file
cp .env.example .env

# 3. Build and start all containers
docker compose up --build

# 4. Verify
curl http://localhost:8005/health
# → {"service":"owner5-application-service","status":"ok"}

# 5. Open Swagger UI
open http://localhost:8005/docs

# 6. Stop
docker compose down
```

---

## How to Seed Data

The seed file runs automatically via Docker Compose on first start  
(`./seed/seed.sql` is mapped to `/docker-entrypoint-initdb.d/002_seed.sql`).

To run manually:

```bash
# Run seed inside the running mysql container
docker exec -i owner5_mysql mysql -u app_user -papp_password application_core < seed/seed.sql
```

Seed inserts:
- `job_3301` → **open** (applications allowed)
- `job_3302` → **closed** (applications blocked — returns 400)
- Sample applications and recruiter notes

---

## Curl Examples

### Health Check
```bash
curl http://localhost:8005/health
```
**Expected:**
```json
{"service": "owner5-application-service", "status": "ok"}
```

---

### Submit Application (success)
```bash
curl -X POST http://localhost:8005/applications/submit \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{
    "job_id":          "job_3301",
    "member_id":       "mem_501",
    "resume_ref":      "s3://bucket/resume-501.pdf",
    "idempotency_key": "mem501-job3301-v1",
    "answers": [{"question_key": "work_auth", "answer_text": "Yes"}]
  }'
```
**Expected `201`:**
```json
{"application_id": "app_abc123", "status": "submitted", "trace_id": "trc_xyz789"}
```

---

### Submit Duplicate Application (409)
```bash
# Run the same command again — same job_id + member_id
curl -X POST http://localhost:8005/applications/submit \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{
    "job_id":          "job_3301",
    "member_id":       "mem_501",
    "resume_ref":      "s3://bucket/resume-501.pdf",
    "idempotency_key": "mem501-job3301-v2"
  }'
```
**Expected `409`:**
```json
{"detail": "Duplicate application — already applied to this job"}
```

---

### Apply to Closed Job (400)
```bash
curl -X POST http://localhost:8005/applications/submit \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{
    "job_id":          "job_3302",
    "member_id":       "mem_502",
    "resume_ref":      "s3://bucket/resume-502.pdf",
    "idempotency_key": "mem502-job3302-v1"
  }'
```
**Expected `400`:**
```json
{"detail": "Cannot apply to closed job"}
```

---

### Get Application
```bash
curl -X POST http://localhost:8005/applications/get \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"application_id": "app_abc123"}'
```

---

### List by Job
```bash
curl -X POST http://localhost:8005/applications/byJob \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"job_id": "job_3301"}'
```

---

### List by Member
```bash
curl -X POST http://localhost:8005/applications/byMember \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"member_id": "mem_501"}'
```

---

### Update Status
```bash
curl -X POST http://localhost:8005/applications/updateStatus \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": "app_abc123",
    "status":         "under_review",
    "updated_by":     "rec_120"
  }'
```
**Expected `200`:**
```json
{"application_id": "app_abc123", "old_status": "submitted", "new_status": "under_review", "trace_id": "trc_..."}
```

**Invalid status → `400`:**
```bash
curl -X POST http://localhost:8005/applications/updateStatus \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"application_id": "app_abc123", "status": "dancing", "updated_by": "rec_120"}'
```

---

### Add Recruiter Note
```bash
curl -X POST http://localhost:8005/applications/addNote \
  -H "Authorization: Bearer owner5-demo-token" \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": "app_abc123",
    "recruiter_id":   "rec_120",
    "note_text":      "Candidate has strong Python and SQL background."
  }'
```
**Expected `201`:**
```json
{"note_id": "note_abc", "application_id": "app_abc123", "status": "note_added"}
```

---

## Expected Failure Responses

| Scenario | HTTP | Response body |
|----------|------|---------------|
| Apply to closed job | 400 | `{"detail": "Cannot apply to closed job"}` |
| Duplicate application | 409 | `{"detail": "Duplicate application — already applied to this job"}` |
| Application not found | 404 | `{"detail": "Application not found"}` |
| Invalid status value | 400 | `{"detail": "Invalid status 'xxx'. Allowed: [...]"}` |

---

## How to Run Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run a single test
pytest tests/test_applications.py::test_health -v
```

Tests use **in-memory SQLite** — no Docker or MySQL required.

All 12 test cases:
1. `test_health` — GET /health returns 200
2. `test_submit_success` — submit to open job returns 201
3. `test_duplicate_application` — duplicate returns 409
4. `test_apply_closed_job` — closed job returns 400
5. `test_get_application` — GET by application_id works
6. `test_by_job` — list by job returns list
7. `test_by_member` — list by member returns list
8. `test_update_status` — status update works
9. `test_invalid_status` — invalid status returns 400
10. `test_add_note` — recruiter note returns 201
11. `test_missing_application` — missing ID returns 404
12. `test_kafka_failure_does_not_crash` — Kafka down → DB still commits → 201

---

## How to Run Benchmark (Scenario B)

**Install k6:**
```bash
brew install k6   # macOS
```

**Start the service first:**
```bash
docker compose up --build -d
```

**Run Scenario B — 4 bar charts:**

```bash
# 1. Base (no Redis fast check — comment out redis check in service for pure base)
k6 run benchmark/apply_benchmark.js \
  -e API_URL=http://localhost:8005 \
  -e SCENARIO=base

# 2. Base + Redis
k6 run benchmark/apply_benchmark.js \
  -e API_URL=http://localhost:8005 \
  -e SCENARIO=redis

# 3. Base + Redis + Kafka
k6 run benchmark/apply_benchmark.js \
  -e API_URL=http://localhost:8005 \
  -e SCENARIO=kafka

# 4. Base + Redis + Kafka + Optimized (connection pooling, indexes)
k6 run benchmark/apply_benchmark.js \
  -e API_URL=http://localhost:8005 \
  -e SCENARIO=optimized

# Save results to JSON
k6 run benchmark/apply_benchmark.js --out json=benchmark_results.json
```

**What is measured:**
- Average latency (ms)
- P95 latency (ms)
- Throughput (requests/second)
- Error rate (%)
- Duplicate blocked count
- Closed-job blocked count

**Load:** 100 concurrent virtual users for 30 seconds.

---

## Kafka Consumer — Run Standalone

```bash
# From the service root
python -m app.kafka.job_consumer
```

If Kafka is unavailable, it logs a clean message and exits gracefully.

---

## Final Evidence Checklist (Submission)

Take screenshots of each item below for your submission report:

- [ ] `GET /health` → 200 response
- [ ] `POST /applications/submit` → 201 with application_id
- [ ] Duplicate apply → 409
- [ ] Closed job apply → 400
- [ ] `POST /applications/get` → full application with answers/notes
- [ ] `POST /applications/byJob` → list of applications
- [ ] `POST /applications/byMember` → list of applications
- [ ] `POST /applications/updateStatus` → old/new status
- [ ] `POST /applications/addNote` → note_id response
- [ ] MySQL schema screenshot (`SHOW TABLES;` in application_core)
- [ ] Redis key screenshot (`redis-cli KEYS "apply:idem:*"`)
- [ ] Kafka event log screenshot (consumer output showing published events)
- [ ] Benchmark result screenshot (4-bar chart: Base, B+S, B+S+K, B+S+K+Opt)
- [ ] Swagger UI screenshot (`/docs`)

---

## Project Context

This service is **Owner 5** in an 8-owner distributed LinkedIn simulation.

| Owner | Service |
|-------|---------|
| Owner 1 | Auth + API Edge |
| Owner 2 | Member Profile |
| Owner 3 | Recruiter & Company |
| Owner 4 | Job Service ← produces Kafka events consumed here |
| **Owner 5** | **Application Service (this repo)** |
| Owner 6 | Messaging + Connections |
| Owner 7 | Analytics + Kafka Host |
| Owner 8 | FastAPI Agent Orchestrator |

**This service only owns `application_core` database. It does not write to any other owner's database.**
