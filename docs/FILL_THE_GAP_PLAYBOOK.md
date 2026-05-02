# Fill the Gap Playbook

This repo already gives you a runnable demo stack, but the main gap is that live service state still goes through `backend/services/shared/persist.py` instead of real repositories backed by MySQL and MongoDB.

## The exact gap

Replace:
- `backend/services/shared/persist.py`

With:
- MySQL repositories for Owners 1 to 5
- MongoDB repositories for Owners 6 to 8
- Redis as cache only
- Kafka as real event transport in runtime paths

Do **not** rewrite everything from scratch. Keep the API routes, request/response models, Kafka topic names, and observability endpoints. Replace the storage layer under them.

---

## 1. Target architecture

### MySQL-backed services
- Owner 1: auth, refresh tokens, idempotency registry
- Owner 2: members, skills, experience, education
- Owner 3: recruiters, companies
- Owner 4: jobs, job_skills
- Owner 5: applications, application_notes

### MongoDB-backed services
- Owner 6: threads, messages, connection_requests, connections
- Owner 7: raw events, rollups, benchmark reports
- Owner 8: ai_tasks, ai_task_steps, ai_results

### Redis-backed caches
- Owner 1: rate-limit / refresh / idempotency hot keys
- Owner 4: jobs:get, jobs:search, jobs:byRecruiter
- Owner 6: unread counters
- Owner 7: analytics dashboard query cache
- Owner 8: task status cache / websocket fanout state

### Kafka runtime paths
- Owner 4 publishes: `job.created`, `job.viewed`, `job.updated`, `job.closed`
- Owner 5 publishes: `application.submitted`, `application.status.updated`, `application.note.added`
- Owner 6 publishes: `thread.opened`, `message.sent`, `connection.requested`, `connection.accepted`, `connection.rejected`
- Owner 7 consumes domain events and produces analytics rollups
- Owner 8 uses `ai.requests` and `ai.results`

---

## 2. Minimal code refactor plan

## Step A: add a repository layer

Create:

```text
backend/services/shared/repositories/
  base.py
  mysql.py
  mongo.py
  owner1_auth_repo.py
  owner2_member_repo.py
  owner3_recruiter_repo.py
  owner4_jobs_repo.py
  owner5_applications_repo.py
  owner6_messaging_repo.py
  owner7_analytics_repo.py
  owner8_ai_repo.py
```

Rules:
- route handlers must not write files directly
- route handlers call service functions
- service functions call repository methods
- repository layer owns all DB queries and transactions

## Step B: keep route contracts stable

Do **not** change endpoint URLs or response envelope shape.

Keep:
- `success`
- `trace_id`
- `data`
- `meta`
- `error.code`
- `error.retryable`

## Step C: move common DB clients into shared helpers

Create:

```text
backend/services/shared/db.py
backend/services/shared/models_sqlalchemy.py
backend/services/shared/mongo_collections.py
```

Use:
- SQLAlchemy for MySQL
- PyMongo or Motor for MongoDB
- redis-py for Redis

---

## 3. Concrete per-service implementation work

## Owner 1 Auth

Replace file-backed storage with MySQL tables:
- `users`
- `refresh_tokens`
- `idempotency_registry`

Implement:
- unique email
- hashed password
- refresh token rotation
- logout revoke
- JWKS publishing stays in code

Also add Redis keys:
- `rate_limit:login:{email}`
- `rate_limit:login_ip:{ip}`
- `idempotency:{route}:{key}`

## Owner 2 Member

Back with MySQL:
- `members`
- `member_skills`
- `member_experience`
- `member_education`

Optional Mongo:
- `member_resume_docs`
- `member_resume_versions`

Implement versioning for `/members/update`.

## Owner 3 Recruiter / Company

Back with MySQL:
- `companies`
- `recruiters`

Implement recruiter/company joins in repo, not in route handlers.

## Owner 4 Jobs

Back with MySQL:
- `jobs`
- `job_skills`

Add Redis cache keys:
- `job:detail:{job_id}`
- `job:search:{filter_hash}`
- `job:byRecruiter:{recruiter_id}:{status}:{page}:{page_size}`

Invalidate on:
- create
- update
- close

## Owner 5 Applications

Back with MySQL:
- `applications`
- `application_notes`

Required:
- unique `(job_id, member_id)`
- transaction around submit
- persist idempotency key for `/applications/submit`
- publish Kafka event after commit or via outbox

Strong recommendation:
Use a small outbox table:
- `event_outbox(id, topic, payload_json, status, created_at)`

## Owner 6 Messaging / Connections

Back with Mongo:
- `threads`
- `messages`
- `connection_requests`
- `connections`

Indexes:
- `threads.participant_key` unique
- `messages(thread_id, sent_at desc)`
- `messages(thread_id, client_message_id)` unique
- `connections.pair_key` unique
- pending request uniqueness for same requester/receiver pair

Redis keys:
- `unread:thread:{thread_id}:{user_id}`
- `unread:user:{user_id}:total`

## Owner 7 Analytics

Back with Mongo:
- `events_raw`
- `job_funnel_rollups`
- `geo_rollups`
- `member_dashboard_rollups`
- `benchmark_reports`

Owner 7 should consume Kafka in a background worker process or background task started on service boot.

## Owner 8 AI

Back with Mongo:
- `ai_tasks`
- `ai_task_steps`
- `ai_task_outputs`

Redis keys:
- `ai:task:{task_id}:status`
- `ai:task:{task_id}:progress`

Keep WebSocket support. Task create should publish to `ai.requests`. Worker consumes and emits to `ai.results`.

---

## 4. Database migrations and init

## MySQL

Keep `infra/mysql/001_init.sql`, but expand it to create all real tables.

Add:
- foreign keys where useful
- unique indexes
- created_at / updated_at
- version columns where optimistic locking is required

Recommended next file:

```text
infra/mysql/002_indexes.sql
infra/mysql/003_seed_helpers.sql
```

## Mongo

Keep `infra/mongo/init.js`, but expand it to create:
- collections
- unique indexes
- TTL indexes only where useful

---

## 5. Make bootstrap fully automatic

Your goal is one command:

```bash
./scripts/bootstrap_local.sh
```

That script should:
1. bring up mysql, mongo, redis, kafka, prometheus, grafana
2. wait until each is healthy
3. run MySQL init scripts
4. run Mongo init script
5. create Kafka topics
6. start all owner services
7. run demo seeding
8. start frontend
9. print URLs

Also add:

```bash
./scripts/reset_all.sh
./scripts/seed_demo.sh
./scripts/seed_perf.sh
```

---

## 6. Fix Kafka the right way

Do not use the in-memory bus for the final repo.

Replace or guard:
- `backend/services/shared/kafka_bus.py`

With:
- real producer using `kafka-python` or `confluent-kafka`
- consumer loops for Owner 7 and Owner 8
- topic creation script in bootstrap or `kafka-init`

Recommended pattern:
- service writes DB first
- writes outbox record in same transaction
- background dispatcher publishes to Kafka
- dispatcher marks outbox row sent

This is much safer than trying to publish directly inside the request before commit.

---

## 7. Caching and cache-hit-rate metrics

You asked for proper caching and hit-rate metrics.

For each service, keep `/ops/cache-stats` and `/ops/metrics`, but back them with real counters.

Track at least:
- cache_hits_total
- cache_misses_total
- cache_writes_total
- cache_invalidations_total
- cache_hit_rate

Per service:
- Owner 4: track hit rate for job detail/search/byRecruiter
- Owner 6: track unread counter cache hits
- Owner 7: analytics widget cache hit rate
- Owner 8: AI task status cache hit rate

Expose them in Prometheus format from `/ops/metrics`.

---

## 8. Tracing and logs

Keep structured JSON logs.

Add fields everywhere:
- `trace_id`
- `span_name`
- `service`
- `route`
- `actor_id`
- `entity_type`
- `entity_id`
- `idempotency_key`
- `event_type`

Make sure the same `trace_id` moves across:
- frontend request
- backend service
- Kafka event
- Owner 7 analytics event storage
- Owner 8 AI task steps

---

## 9. Tests to add before calling it done

## API tests
- auth register/login/refresh/logout
- member CRUD + search
- recruiter/company CRUD
- job create/get/update/search/close/byRecruiter
- application submit/get/byJob/byMember/updateStatus/addNote
- messaging thread open/get/byUser/list/send
- connection request/accept/reject/list/mutual
- analytics dashboards
- AI create/get/approve/reject/websocket

## Idempotency tests
- duplicate register key
- duplicate application submit key
- duplicate message send `client_message_id`
- duplicate AI task create key

## Failure mode tests
- duplicate user
- duplicate application
- apply to closed job
- message retry after failure
- Kafka consumer replay
- stale version conflict for member/job update

## Observability tests
- `/ops/healthz`
- `/ops/cache-stats`
- `/ops/metrics`
- trace_id propagation in logs and events

---

## 10. Frontend completion

The frontend is included, but you should tighten it after backend persistence is real.

Owner 9 should:
- replace mock/demo assumptions with real login flow
- persist access/refresh tokens
- wire job search/apply screens to real API states
- wire messaging UI to Owner 6
- wire AI task status and WebSocket progress to Owner 8
- add pages for Grafana/analytics links if helpful

---

## 11. Multi-account AWS completion

For AWS, do not deploy the current local `docker-compose.yml` as-is across accounts.

Use the existing per-account templates under:
- `deploy/aws_accounts/`

Then finish them so each account has:
- one EC2 instance or ECS service
- environment file pointing to shared public endpoints
- security groups allowing only required traffic
- Owner 1 publishes JWKS publicly
- Owner 7 exposes Kafka/bootstrap for allowed service accounts
- Owner 9 hosts frontend separately

Recommended order:
1. Owner 7 Kafka/analytics
2. Owner 1 auth/JWKS
3. Owners 2 to 6
4. Owner 8 AI
5. Owner 9 frontend

---

## 12. Best execution order for you

If you want the shortest path to a real end-to-end system, do this exact order:

1. replace `persist.py` with repository interfaces
2. implement real MySQL repositories for Owners 1 to 5
3. implement real Mongo repositories for Owners 6 to 8
4. add Redis cache reads/writes and invalidation
5. replace in-memory Kafka with real Kafka producer/consumer code
6. make `bootstrap_local.sh` fully automatic
7. make demo seeding hit real DBs
8. run API test suite
9. run end-to-end local smoke tests
10. deploy Owner 7, then Owner 1, then the rest on AWS
11. deploy Owner 9 frontend
12. run JMeter from Owner 9

---

## 13. If you want one concrete first task

Your first task should be:

> Remove all file-backed persistence from `backend/services/shared/persist.py` and replace it with repository interfaces plus real MySQL/Mongo implementations, while keeping every existing API route and response contract unchanged.

That single change is the biggest gap.

