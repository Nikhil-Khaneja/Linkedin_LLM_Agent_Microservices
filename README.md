# Owner 7 — Analytics + Kafka Host Service

> LinkedIn Simulation + Agentic AI Services — 8-Account AWS Architecture  
> **Jira tickets:** LI-07 · LI-15 · LI-23 · LI-31

Owner 7 is the analytics hub and **shared Kafka broker** for the entire 8-owner distributed LinkedIn-like platform. Every other owner's service connects to Kafka hosted here and publishes events that this service aggregates into dashboards and benchmark artifacts.

---

## Service Ownership Overview

| Owner | Service | Stack |
|---|---|---|
| Owner 1 | Auth + API Edge | EC2 + MySQL + Redis |
| Owner 2 | Member Profile | EC2 + MySQL + MongoDB |
| Owner 3 | Recruiter & Company | EC2 + MySQL |
| Owner 4 | Job | EC2 + MySQL + Redis |
| Owner 5 | Application | EC2 + MySQL + Redis |
| Owner 6 | Messaging + Connections | EC2 + MongoDB + Redis |
| **Owner 7** | **Analytics + Kafka Host** | **EC2 + MongoDB + Redis + Kafka** |
| Owner 8 | FastAPI Agent Orchestrator | EC2 + MongoDB + Redis |

Owner 7 is the **only** member who additionally hosts the shared Kafka runtime. All other services stay fully autonomous.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                   Owner 7 EC2 — Analytics Service                │
│                                                                  │
│   Browser → React Frontend (port 3000)                          │
│                  │ nginx /analytics-api/ proxy                   │
│                  ▼                                               │
│          FastAPI API (port 8000)                                 │
│                  │                                               │
│     ┌────────────┼───────────────────┐                          │
│     ▼            ▼                   ▼                          │
│  MongoDB      Redis               Redpanda                      │
│  (27017)     (6379)              (19092 ext)                    │
│  events_raw  analytics cache     Kafka broker                   │
│  rollups     5 min TTL           for all 8 owners               │
└──────────────────────────────────────────────────────────────────┘
         ▲ Kafka events from Owners 1–6, 8
```

**Redpanda** is used as the Kafka broker — 100% Kafka API-compatible with lower memory overhead. All other owners connect using standard Kafka clients pointed at `<owner7-ec2>:19092`.

---

## Local Quick Start

```bash
# 1. Clone and start all containers
docker compose up -d

# 2. Seed 30 days of sample analytics data
python3 scripts/seed_events.py

# 3. Open frontend
open http://localhost:3000

# 4. Swagger API docs
open http://localhost:8000/docs

# 5. Redpanda Console (topic browser)
open http://localhost:8080
```

**Dummy user for local dev** (paste in browser console after opening http://localhost:3000):
```js
localStorage.setItem('access_token', 'eyJhbGciOiAiSFMyNTYifQ.eyJ1c2VySWQiOiJkZXZfMDAxIiwidXNlclR5cGUiOiJyZWNydWl0ZXIiLCJleHAiOjk5OTk5OTk5OTl9.fake');
localStorage.setItem('user_data', JSON.stringify({"userId":"dev_001","userType":"recruiter","email":"nikhil@owner7.dev"}));
location.reload();
```

---

## Services & Ports

| Container | Port | Description |
|---|---|---|
| `analytics-api` | 8000 | FastAPI backend |
| `frontend` | 3000 | React UI via nginx |
| `mongodb` | 27017 | Event store + rollup collections |
| `redis` | 6379 | Analytics query cache (5 min TTL) |
| `redpanda` | 19092 | Kafka-compatible broker (external) |
| `redpanda` | 9092 | Kafka broker (internal Docker network) |
| `console` | 8080 | Redpanda Console UI |

---

## API Reference (LI-07, LI-15)

All request/response bodies use JSON. No authentication required during local development.

### Health Check

```
GET /health
```

```json
{ "status": "ok", "service": "owner7-analytics" }
```

---

### 1. Ingest Event

```
POST /events/ingest
```

Accepts a UI or service event using the **standard Kafka envelope** agreed upon by all 8 owners. Stores in MongoDB and re-publishes to `analytics.<event_type>` topic.

Returns **HTTP 409** if the `idempotency_key` was already processed (safe for at-least-once retry).

**Request:**
```json
{
  "event_type": "job.viewed",
  "actor_id": "mem_501",
  "trace_id": "trc_1001",
  "entity": {
    "entity_type": "job",
    "entity_id": "job_3301"
  },
  "payload": {
    "city": "San Jose",
    "state": "CA",
    "source": "web"
  },
  "idempotency_key": "mem501-job3301-view-v1"
}
```

**Response 200:**
```json
{ "accepted": true, "event_id": "evt_44001" }
```

**Response 409 — duplicate:**
```json
{
  "detail": {
    "error": "duplicate_event",
    "message": "Event with this idempotency_key already processed",
    "original_event_id": "evt_44001"
  }
}
```

---

### 2. Top Jobs

```
POST /analytics/jobs/top
```

Returns top N jobs ranked by a chosen metric. Redis-cached for 5 minutes.

**Request:**
```json
{
  "metric": "applications",
  "days": 30,
  "limit": 10
}
```

`metric` options: `applications` | `views` | `saves`

**Response:**
```json
{
  "jobs": [
    { "job_id": "job_3301", "count": 142 },
    { "job_id": "job_2201", "count": 97 }
  ],
  "metric": "applications",
  "limit": 10
}
```

---

### 3. View-Save-Apply Funnel

```
POST /analytics/funnel
```

Calculates conversion funnel for a specific job or all jobs across the lookback window.

**Request:**
```json
{
  "job_id": "job_3301",
  "days": 30
}
```

`job_id` is optional — omit to aggregate across all jobs.

**Response:**
```json
{
  "views": 540,
  "saves": 87,
  "applications": 34,
  "view_to_save_rate": 0.1611,
  "save_to_apply_rate": 0.3908,
  "view_to_apply_rate": 0.063
}
```

---

### 4. Geo Distribution

```
POST /analytics/geo
```

City/state breakdown of job activity. All fields optional — combine freely for drill-down.

**Request:**
```json
{
  "job_id": "job_3301",
  "city": "San Jose",
  "state": "CA",
  "event_type": "application.submitted",
  "days": 30,
  "limit": 20
}
```

`event_type` defaults to both `job.viewed` and `application.submitted` when omitted.

**Response:**
```json
{
  "distribution": [
    { "location": "San Jose, CA", "count": 78 },
    { "location": "New York, NY", "count": 45 },
    { "location": "Austin, TX", "count": 31 }
  ]
}
```

---

### 5. Member Dashboard

```
POST /analytics/member/dashboard
```

Returns engagement metrics rolled up for a specific member.

**Request:**
```json
{ "member_id": "mem_501" }
```

**Response:**
```json
{
  "profile_views": 24,
  "applications_sent": 7,
  "connections": 12,
  "messages_received": 5,
  "job_matches": 0
}
```

`job_matches` is populated by Owner 8 (AI service) after integration.

---

### 6. Benchmark Report

```
POST /benchmarks/report
```

Stores a JMeter/load test result and publishes `benchmark.completed` to Kafka. Used to assemble presentation artifacts (LI-31).

**Request:**
```json
{
  "scenario": "A",
  "owner_id": "owner7",
  "service_name": "analytics-service",
  "results": {
    "total_requests": 10000,
    "throughput_rps": 182.7,
    "avg_response_ms": 4,
    "error_rate_pct": 0.0
  },
  "metadata": {
    "endpoint": "/events/ingest",
    "threads": 50,
    "ramp_time_sec": 30
  }
}
```

`scenario`: `"A"` or `"B"` — aligns with the project benchmark plan.

**Response:**
```json
{ "benchmark_id": "bench_9f6ac596", "status": "stored" }
```

---

## Kafka Integration

### Broker Connection

| Context | Address |
|---|---|
| Internal Docker network | `redpanda:9092` |
| Localhost / other owners (EC2) | `<owner7-ec2-public-ip>:19092` |

### Topics Owner 7 Consumes (23 topics)

| Source Owner | Topics |
|---|---|
| Owner 1 — Auth | `user.created`, `user.logout` |
| Owner 2 — Member Profile | `member.created`, `member.updated`, `profile.viewed` |
| Owner 3 — Recruiter | `recruiter.created`, `recruiter.updated` |
| Owner 4 — Job | `job.created`, `job.updated`, `job.closed`, `job.viewed`, `job.search.executed` |
| Owner 5 — Application | `application.submitted`, `application.status.updated`, `application.note.added` |
| Owner 6 — Messaging | `message.sent`, `thread.opened`, `connection.requested`, `connection.accepted` |
| Owner 8 — AI Agent | `ai.requested`, `ai.completed`, `ai.approved`, `ai.rejected` |

### Topics Owner 7 Publishes

| Topic | Trigger |
|---|---|
| `analytics.<event_type>` | Every successfully ingested event |
| `benchmark.completed` | Every benchmark report submission |

---

## Standard Kafka Event Envelope

All 8 owners agreed on this shared contract. Every event published to Kafka must follow this structure:

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
  "payload": {
    "job_id": "job_3301",
    "member_id": "mem_501",
    "resume_ref": "s3://bucket/resume-501.pdf"
  },
  "idempotency_key": "mem501-job3301-v1"
}
```

- `trace_id` is preserved end-to-end across all services and AI workflows
- Every consumer must be **idempotent** and safe under at-least-once delivery
- `idempotency_key` is optional but strongly recommended for mutation events

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `events_raw` | Raw ingested events with full envelope |
| `recruiter_dash_rollups` | Daily rollup counters per job (views, applies, saves) |
| `member_dash_rollups` | Daily rollup counters per member (profile views, messages, connections) |
| `benchmark_runs` | Stored JMeter benchmark results |

**Key indexes:**
- `events_raw`: `{ event_type, timestamp }`, `{ idempotency_key }` (unique sparse)
- `recruiter_dash_rollups`: `{ job_id, date }`
- `member_dash_rollups`: `{ member_id, date }`

---

## Performance Benchmarks (LI-23, LI-31)

Run with JMeter via Docker:

```bash
# Run both scenarios (Scenario A + B)
docker compose --profile benchmark run --rm jmeter

# Scenario A only — ingest stress test
docker compose --profile benchmark run --rm -e SCENARIO=A jmeter

# Scenario B only — analytics query load test
docker compose --profile benchmark run --rm -e SCENARIO=B jmeter
```

### Results (local M-series Mac)

| Scenario | Endpoint(s) | Threads | Requests | Throughput | Avg Latency | Error Rate |
|---|---|---|---|---|---|---|
| A — Ingest | `POST /events/ingest` | 50 | 10,000 | **186 req/s** | 3ms | **0%** |
| B — Queries | All 4 analytics endpoints | 30 | 12,000 | **117 req/s** | 2ms | **0%** |

Results saved to `jmeter/results/` as CSV + HTML reports. Summaries auto-posted to `/benchmarks/report`.

> Per the project spec: Owner 4 owns Scenario A (job search + Redis cache), Owner 5 owns Scenario B (apply submit). Owner 7 collects and assembles final benchmark figures for presentation.

---

## Running Tests

```bash
# Install dependencies (no Docker needed for unit tests)
pip install -r requirements.txt

# Full suite — 40 tests
pytest tests/ -v

# Unit tests only (mocked DB/Redis/Kafka)
pytest tests/test_units.py -v

# API integration tests (requires running service)
pytest tests/test_api.py -v
```

Test modules:
- `test_units.py` — covers settings, Pydantic models, DB helpers, analytics service, Kafka consumer via `AsyncMock`
- `test_api.py` — covers all endpoints including idempotency 409 enforcement

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:19092` | Redpanda/Kafka broker address |
| `KAFKA_CONSUMER_GROUP` | `owner7-analytics` | Consumer group ID |
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB` | `analytics` | MongoDB database name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `REDIS_CACHE_TTL` | `300` | Query cache TTL in seconds |
| `ENV` | `development` | Environment name |

---

## Project Structure

```
owner7-analytics-service/
├── app/
│   ├── api/routes.py              # 6 API endpoints (health + 5 analytics)
│   ├── config/settings.py         # Env-based config via pydantic-settings
│   ├── consumers/
│   │   └── event_consumer.py      # aiokafka consumer — 23 cross-owner topics
│   ├── models/events.py           # KafkaEventEnvelope + request/response models
│   ├── services/
│   │   └── analytics_service.py   # Business logic + Redis caching layer
│   └── utils/db.py                # MongoDB motor + Redis async connection helpers
├── frontend/
│   ├── Dockerfile                 # Multi-stage: node build → nginx serve
│   ├── nginx.conf                 # Reverse proxy /analytics-api/ → FastAPI
│   └── src/
│       ├── pages/                 # 10 React pages (Analytics, Recruiter, Jobs, etc.)
│       ├── context/AuthContext.js # localStorage token (full OAuth at integration time)
│       └── config/api.js          # Per-owner service URL config
├── jmeter/
│   ├── Dockerfile                 # JMeter 5.6.3 on eclipse-temurin:21-jre-jammy
│   ├── run_tests.sh               # Waits for API health, runs plans, posts results
│   └── plans/
│       ├── scenario_a_ingest.jmx  # 50 threads × 200 loops on /events/ingest
│       └── scenario_b_queries.jmx # 30 threads × 100 loops on analytics endpoints
├── scripts/seed_events.py         # Seeds 30 days of cross-owner synthetic events
├── tests/
│   ├── test_units.py              # 40 unit tests — no Docker required
│   └── test_api.py                # API integration tests
├── docker-compose.yml             # 6 core services + benchmark profile
├── Dockerfile                     # FastAPI app image
├── pytest.ini                     # asyncio_mode = auto
└── requirements.txt
```

---

## EC2 Deployment

Owner 7 EC2 hosts both the analytics service and the shared Kafka broker that all other owners connect to.

### Security Group Rules (Owner 7 EC2)

| Port | Protocol | Source | Purpose |
|---|---|---|---|
| 19092 | TCP | All owner EC2 IPs | Kafka external access |
| 8000 | TCP | All owner EC2 IPs + public | Analytics API |
| 3000 | TCP | Public | React frontend |
| 8080 | TCP | Team only | Redpanda Console |
| 27017 | TCP | localhost only | MongoDB (never expose) |
| 6379 | TCP | localhost only | Redis (never expose) |

### Connecting Other Owners to Kafka

All other owners configure their Kafka producers/consumers with:
```
bootstrap.servers = <owner7-ec2-public-ip>:19092
```

### Inter-Service URL Configuration

When other owners' services are live on EC2, update `frontend/src/config/api.js`:

```js
const BASE = {
  analytics:   process.env.REACT_APP_ANALYTICS_URL || 'http://localhost:8000',
  auth:        process.env.REACT_APP_AUTH_URL      || 'http://<owner1-ec2>:3001',
  member:      process.env.REACT_APP_MEMBER_URL    || 'http://<owner2-ec2>:3002',
  recruiter:   process.env.REACT_APP_RECRUITER_URL || 'http://<owner3-ec2>:3003',
  job:         process.env.REACT_APP_JOB_URL       || 'http://<owner4-ec2>:3004',
  application: process.env.REACT_APP_APP_URL       || 'http://<owner5-ec2>:3005',
  messaging:   process.env.REACT_APP_MSG_URL       || 'http://<owner6-ec2>:3006',
  ai:          process.env.REACT_APP_AI_URL        || 'http://<owner8-ec2>:3008',
};
```

Pass EC2 URLs as build args:
```bash
docker compose build \
  --build-arg REACT_APP_AUTH_URL=http://<owner1-ec2>:3001 \
  --build-arg REACT_APP_ANALYTICS_URL=http://<owner7-ec2>:8000 \
  frontend
```

---

## Jira Tickets

| Ticket | Week | Summary |
|---|---|---|
| LI-07 | 1 | Freeze event envelope, bootstrap EC2, MongoDB, Redis, Kafka |
| LI-15 | 2 | Implement `/events/ingest` and placeholder dashboard endpoints |
| LI-23 | 3 | Build dashboard rollups from Kafka event streams; verify cross-account broker |
| LI-31 | 4 | Generate dashboard screenshots + benchmark summary exports for presentation |

---

## AWS Free-Tier Notes

- Use a single `t2.micro` or `t3.micro` EC2 instance
- Disable T3 Unlimited mode to avoid CPU-credit charges
- Use one public IPv4 only — delete idle resources immediately
- Keep EBS disk small; avoid unnecessary snapshots
- Do **not** provision NAT Gateway, ALB, or MSK — not needed for a class demo
