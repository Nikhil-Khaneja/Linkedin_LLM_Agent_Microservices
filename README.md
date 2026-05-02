# LinkedIn Clone - Event-Driven Class Project Monorepo

This repository is a full-stack class-project implementation aligned to the uploaded LinkedIn Simulation + Agentic AI specification: eight backend owner services, one shared React frontend, Kafka-centered async workflows, Redis caching, Mongo/MySQL split, analytics, and a FastAPI AI orchestrator.

## Team ownership model

- Owner 1: Auth + API edge
- Owner 2: Member profile service
- Owner 3: Recruiter + company service
- Owner 4: Job service
- Owner 5: Application service
- Owner 6: Messaging + connections service
- Owner 7: Analytics + logging service and shared Kafka host
- Owner 8: AI orchestrator service
- **Owner 9: Frontend deployment + JMeter + release verification**

## What is included

- Shared React frontend in `frontend/`
- Eight FastAPI backend services in `backend/services/`
- Kafka topic publishing and consumption for async flows
- Redis-backed caches for hot reads and counters
- MySQL and Mongo initialization scripts under `infra/`
- Automated bootstrap scripts for schema, indexes, Kafka topics, and readiness checks under `scripts/`
- Owner 9 frontend and JMeter deployment notes under `deploy/aws_accounts/owner9_frontend/`
- Prometheus + Grafana observability configuration under `observability/`
- API smoke tests under `tests/api/`
- JMeter starter plans under `tests/jmeter/`
- Local + AWS deployment docs under `docs/`

## Runtime modes

### 1. Local Docker mode
- Kafka KRaft in Docker Compose
- Redis-backed cache mode
- Prometheus + Grafana ops dashboards
- Frontend served by Vite dev server

### 2. Sandbox test mode
- MySQL-backed relational persistence for Owners 1-5
- In-memory document store and event bus for sandbox tests only
- In-memory cache and event/document modes are test-only

## Built-in ops endpoints

Every backend service exposes:
- `GET /ops/healthz`
- `GET /ops/cache-stats`
- `GET /ops/metrics`

Each service emits structured JSON request logs with trace IDs and request timing.

## Redis caching implemented

- Owner 1: login failure rate-limit metadata
- Owner 4: job detail, search, recruiter job list cache + invalidation
- Owner 6: unread counters
- Owner 7: analytics response cache
- Owner 8: AI task state cache

`/ops/cache-stats` reports lookups, hits, misses, hit rate, and namespace-level breakdown per service.

## Quick local start

```bash
cp .env.example .env
chmod +x scripts/bootstrap_local.sh
./scripts/bootstrap_local.sh
```

Open:
- Frontend: `http://localhost:5173`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Service docs:
- Owner 1: `http://localhost:8001/docs`
- Owner 4: `http://localhost:8004/docs`
- Owner 6: `http://localhost:8006/docs`
- Owner 7: `http://localhost:8007/docs`
- Owner 8: `http://localhost:8008/docs`

## Bearer authorization

Protected APIs now validate RS256 bearer JWTs.

- Owner 1 issues access tokens on `/auth/register`, `/auth/login`, and `/auth/refresh`.
- Other services validate those tokens offline using the shared JWKS/public key configuration.
- For separate AWS accounts, set `OWNER1_JWKS_URL` in every backend service to the public JWKS URL exposed by Owner 1.

## Tests run in sandbox

- `python3 -m compileall backend`
- `pytest tests/api -q`

Results are captured in:
- `tests/SANDBOX_TEST_RESULTS.txt`
- `tests/last_pytest_run.txt`

## Recommended docs to read next

- `docs/architecture.md`
- `docs/observability.md`
- `docs/local_and_aws_run.md`
- `docs/aws_multi_account_deploy.md`
- `docs/owner9_frontend_testing.md`

## Current status

This package now uses repository-backed persistence instead of the deprecated JSON file store:
- Owners 1-5 run through the shared relational repository layer
- Owners 6-8 run through the shared document repository layer
- `services.shared.persist` remains only as a deprecated guard so old imports fail loudly
- Kafka memory mode is test-only; non-test environments must use Kafka

The strongest validation completed in the sandbox is:
- compile check
- full API smoke suite
- messaging idempotency
- connection graph flow
- observability endpoints

Detailed handoff docs are still included in:
- `docs/COPILOT_HANDOFF_LINKEDIN_CLONE.md`
- `docs/FILL_THE_GAP_PLAYBOOK.md`

## Automated bootstrap files

- `scripts/bootstrap_local.sh`
- `scripts/wait_for_stack.py`
- `scripts/apply_mysql_schema.sh`
- `scripts/apply_mongo_init.sh`
- `scripts/create_kafka_topics.sh`
- `docs/DB_SETUP_AUTOMATION.md`


## Review fixes completed in this bundle

- **Transactional outbox path**: Owners 4 and 5 now persist domain writes and outbox rows in the same relational transaction. Owners 6 and 8 use a durable document outbox plus background dispatch.
- **Materialized analytics rollups**: Owner 7 now updates `events_rollup` incrementally on ingest/consume and reads dashboards from rollups instead of scanning raw events.
- **Cross-account validation tooling**: run `python3 deploy/aws_accounts/validate_multi_account.py --env-dir deploy/aws_accounts/env` before deploying the separate AWS owner accounts.
- **Frontend production bundle**: a prebuilt static bundle is included in `frontend/dist/` and can be served directly by Owner 9.

## Validation completed in sandbox

- `python3 -m compileall backend`
- `pytest tests/api -q` -> 5 passed
- `python3 deploy/aws_accounts/validate_multi_account.py --env-dir deploy/aws_accounts/env` -> OK
- `./scripts/build_frontend_static.sh`


## Applied local fixes
- MySQL 8.4-compatible schema/index scripts
- Removed deprecated mysql_native_password compose flag
- Added cryptography dependency for RS256 JWT/JWKS
- Added CORS middleware for local frontend calls
- Fixed MySQL named parameter adaptation in shared relational layer


## Phase 1 refactor additions
- Shared React frontend from the uploaded `linkedin-final.zip`, patched to call local Python services on ports 8001-8008.
- `auth_service` refactored into app/routes/services/repositories/core/middleware.


## AWS note
- This bundle keeps MySQL as the source of truth and Redis as a cache.
- Use managed RDS/Aurora for MySQL and ElastiCache for Redis in AWS.
