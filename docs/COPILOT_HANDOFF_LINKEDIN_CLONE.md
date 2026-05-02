# GitHub Copilot Handoff - Finish and Harden the LinkedIn Clone Monorepo

You are working inside the repository `linkedin_clone_owner9_observability`.
Your job is to turn the current class-project starter into a **fully runnable local stack** and a **clean multi-account AWS deployment baseline**.

## 1. What exists already

The repo already contains:
- `frontend/` React + Vite app
- `backend/services/owner1_auth` through `owner8_ai`
- `docker-compose.yml`
- `infra/mysql/001_init.sql`
- `infra/mongo/init.js`
- `scripts/bootstrap_local.sh`
- `tests/api/*`
- `tests/jmeter/*`
- `observability/prometheus/*`
- `observability/grafana/*`
- `deploy/aws_accounts/*`

## 2. Critical truth about the current code

The repo **boots as a demo stack**, but it is **not yet fully wired to real persistence**.

Current gaps:
1. The backend services still use **file-backed JSON persistence** through:
   - `backend/services/shared/persist.py`
2. The system can use real Kafka and Redis in Docker mode, but the data layer is still not real MySQL/Mongo.
3. MySQL and Mongo containers are present, but the service code does not yet read and write through proper repositories/ORM/driver integration.
4. The frontend exists, but it should be checked end-to-end against the final API behavior after persistence is upgraded.

## 3. Your objective

Make the repository satisfy these conditions:

### Local runtime goal
Running:
```bash
cp .env.example .env
chmod +x scripts/bootstrap_local.sh
./scripts/bootstrap_local.sh
```
should result in:
- all infra containers healthy
- all services healthy
- frontend reachable on `http://localhost:5173`
- Prometheus reachable on `http://localhost:9090`
- Grafana reachable on `http://localhost:3000`
- demo seed data loaded
- basic end-to-end flows working

### Backend architecture goal
Keep the existing service split:
- owner1_auth
- owner2_member
- owner3_recruiter
- owner4_jobs
- owner5_applications
- owner6_messaging
- owner7_analytics
- owner8_ai
- owner9_frontend is docs/deploy/testing ownership only

Use event-driven architecture and preserve Kafka topic flow.

## 4. Required implementation tasks

### Task A - Replace file persistence with real repositories

#### MySQL-backed services
Use SQLAlchemy or SQLModel with MySQL for:
- owner1_auth
- owner2_member
- owner3_recruiter
- owner4_jobs
- owner5_applications

Create repository modules and models for:
- users
- refresh_tokens
- members
- member_skills
- member_experience
- member_education
- recruiters
- companies
- jobs
- job_skills
- applications
- application_notes

Use real tables created by migration/init scripts.

#### Mongo-backed services
Use Motor or PyMongo for:
- owner6_messaging
- owner7_analytics
- owner8_ai

Collections should include:
- threads
- messages
- connection_requests
- connections
- events_raw
- events_rollup
- ai_tasks
- ai_task_steps
- benchmarks

### Task B - Keep Redis caching and make it real

The existing cache module already supports Redis mode. Keep that design and ensure the following are actively used and correct:
- Owner 1: login rate-limit metadata
- Owner 4: job detail/search/recruiter job list cache + invalidation
- Owner 6: unread counters
- Owner 7: analytics widget cache
- Owner 8: AI task progress cache

Requirements:
- cache invalidation must happen after writes
- `/ops/cache-stats` must return accurate hit/miss/hit-rate numbers
- Redis outages must degrade safely to memory fallback or direct DB reads

### Task C - Keep Kafka in the runtime path

Do not remove Kafka.
Use the existing `apache/kafka:4.2.0` KRaft-based setup.

Required topics:
- user.created
- member.created
- member.updated
- member.deleted
- job.created
- job.viewed
- job.updated
- job.closed
- application.submitted
- application.status.updated
- application.note.added
- thread.opened
- message.sent
- connection.requested
- connection.accepted
- connection.rejected
- analytics.normalized
- benchmark.completed
- ai.requests
- ai.results
- ai.rejected

Required producer/consumer responsibilities:
- Owner 4 publishes job events
- Owner 5 publishes application events
- Owner 6 publishes messaging/connection events
- Owner 7 consumes domain events and writes analytics/event rollups
- Owner 8 consumes `ai.requests`, publishes `ai.results`, and supports task status streaming

### Task D - Preserve auth model

All protected APIs should require bearer auth except the known public endpoints.
Use Owner 1 as the issuer/JWKS authority.

At minimum:
- keep `.well-known/jwks.json`
- keep dev-token compatibility for local testing
- preserve role checks and ownership/participant checks

### Task E - Make the frontend usable end-to-end

The frontend must support at least these demo flows:
1. register or mock login
2. create member profile
3. create recruiter/company
4. create job
5. search/view job
6. apply to a job
7. open a thread + send messages
8. request/accept connection
9. run an AI task and observe status/progress
10. view analytics endpoints via UI or admin page

If necessary, adjust `frontend/src/api.ts` and `frontend/src/App.tsx`.

### Task F - Strengthen observability

Keep and extend:
- structured JSON logs
- `trace_id` propagation
- request timing logs
- `/ops/healthz`
- `/ops/cache-stats`
- `/ops/metrics`

Also ensure Prometheus metrics include:
- request count
- request latency
- cache hits
- cache misses
- cache hit rate
- Kafka publish success/failure counts
- Kafka consume success/failure counts

Grafana dashboards should include:
- service request overview
- cache hit rate by service
- top slow endpoints
- event throughput

## 5. Acceptance criteria

The work is done only when all of the following are true.

### A. Local boot
This succeeds without manual DB creation:
```bash
./scripts/bootstrap_local.sh
```

### B. Services respond
These URLs open successfully:
- `http://localhost:8001/docs`
- `http://localhost:8004/docs`
- `http://localhost:8005/docs`
- `http://localhost:8006/docs`
- `http://localhost:8007/docs`
- `http://localhost:8008/docs`
- `http://localhost:5173`
- `http://localhost:9090`
- `http://localhost:3000`

### C. End-to-end flows work
1. Recruiter creates a job
2. Member searches and views the job
3. Member submits an application
4. Owner 5 publishes `application.submitted`
5. Owner 7 records analytics event
6. Member/recruiter open a thread
7. Message send is idempotent
8. Connection request / accept works
9. AI task create -> Kafka -> result -> status retrieval works

### D. Tests pass
- existing pytest tests pass
- add real DB integration tests
- add Kafka flow integration tests
- add cache stats validation tests

### E. No file persistence remains in the live path
`persist.py` should not be the main storage path for running services.
It may remain only for tests if explicitly isolated.

## 6. Files you will likely need to edit

### High priority
- `backend/services/shared/persist.py`
- `backend/services/shared/common.py`
- `backend/services/shared/cache.py`
- `backend/services/shared/kafka_bus.py`
- `backend/services/shared/observability.py`
- all `backend/services/owner*/main.py`
- `docker-compose.yml`
- `scripts/bootstrap_local.sh`
- `scripts/seed_demo_data.py`
- `scripts/seed_perf_data.py`
- `infra/mysql/001_init.sql`
- `infra/mongo/init.js`
- `frontend/src/api.ts`
- `frontend/src/App.tsx`
- `tests/api/*`

### New files you should create
- `backend/services/shared/db_mysql.py`
- `backend/services/shared/db_mongo.py`
- `backend/services/shared/models_sql.py`
- `backend/services/shared/repos_*`
- `backend/services/shared/repos_mongo_*`
- `infra/mysql/002_indexes.sql`
- `infra/mysql/003_seed_helpers.sql` if useful
- `docs/LOCAL_RUN_READY.md`
- `docs/AWS_MULTI_ACCOUNT_RUNBOOK.md`

## 7. Seed data expectations

Create both:
- demo seed data
- perf seed data

### Demo seed minimums
- 5 recruiters
- 10 members
- 20 jobs
- 30 applications
- 10 threads
- 50 messages
- 10 connection requests
- 5 AI tasks
- analytics events for recruiter/member dashboards

### Perf seed minimums
- 10,000 members
- 10,000 recruiters or realistic scaled subset
- 10,000 jobs
- realistic application/event/message volumes

## 8. Coding standards

Write code like a senior backend engineer:
- no hidden magic
- explicit repositories and service layers where useful
- idempotent write paths where required
- clear error envelopes matching the API style
- invalidate cache after state changes
- avoid copy-pasted auth logic; centralize it
- make background consumers restart-safe
- avoid fragile startup races

## 9. Final deliverables expected from you

When finished, produce:
1. code changes
2. passing tests
3. updated docs
4. a short summary of:
   - what changed
   - what flows now work end-to-end
   - how to run locally
   - how to deploy per AWS account
   - any known remaining risks

## 10. First actions to take

Start in this order:
1. inspect current `persist.py` usage across all services
2. replace Owner 4 and Owner 5 with real MySQL repositories first
3. replace Owner 6 with Mongo + Redis-backed unread counters
4. replace Owner 7 analytics event store with Mongo
5. replace Owner 8 AI task storage with Mongo
6. update seed scripts for real DBs
7. update tests to run against the real stack
8. verify `bootstrap_local.sh`
9. verify frontend flows
10. update AWS docs

