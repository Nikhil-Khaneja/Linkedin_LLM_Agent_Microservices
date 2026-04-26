# Owner 7 — Analytics & Benchmarking Service

Microservice #7 in the 8-owner LinkedIn-like distributed system.  
Responsibilities: event ingestion, analytics rollups, Kafka hosting (Redpanda), and performance benchmarking.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Owner 7 Analytics Service               │
│                                                         │
│  React Frontend (port 3000)                             │
│       │ nginx /analytics-api/ proxy                     │
│       ▼                                                 │
│  FastAPI (port 8000)                                    │
│       │                                                 │
│  ┌────┴────────────────────────────────────┐            │
│  │  MongoDB (port 27017)                   │            │
│  │  Redis   (port 6379)  — query cache     │            │
│  │  Redpanda (port 19092) — Kafka broker   │            │
│  └─────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

**Redpanda** is used as the Kafka broker (100% Kafka API-compatible). All other owners connect using standard Kafka clients with bootstrap server `<host>:19092`.

---

## Services & Ports

| Service | Port | Description |
|---|---|---|
| FastAPI analytics API | 8000 | Main backend |
| React frontend | 3000 | UI served via nginx |
| MongoDB | 27017 | Event store + rollups |
| Redis | 6379 | Analytics query cache (5 min TTL) |
| Redpanda | 19092 | Kafka-compatible broker (external) |
| Redpanda Console | 8080 | Topic browser UI |

---

## Quick Start

```bash
# 1. Start all services
docker compose up -d

# 2. Seed 30 days of sample data
python3 scripts/seed_events.py

# 3. Open frontend
open http://localhost:3000

# 4. API docs (Swagger)
open http://localhost:8000/docs
```

---

## API Reference

### Health Check

```
GET /health
```

Response:
```json
{ "status": "ok", "service": "owner7-analytics" }
```

---

### 1. Ingest Event

```
POST /events/ingest
```

Accepts a Kafka event envelope, stores it in MongoDB, and re-publishes to `analytics.<event_type>` topic.  
Returns HTTP **409** if `idempotency_key` was already processed.

**Request body:**
```json
{
  "event_type": "job.viewed",
  "actor_id": "mem_001",
  "trace_id": "trace-abc123",
  "entity": {
    "entity_type": "job",
    "entity_id": "job_001"
  },
  "payload": {
    "city": "San Jose",
    "state": "CA",
    "source": "web"
  },
  "idempotency_key": "unique-key-001"
}
```

**Response (200):**
```json
{ "accepted": true, "event_id": "evt_a1b2c3d4" }
```

**Response (409 — duplicate):**
```json
{
  "detail": {
    "error": "duplicate_event",
    "message": "Event with this idempotency_key already processed",
    "original_event_id": "evt_a1b2c3d4"
  }
}
```

---

### 2. Top Jobs

```
POST /analytics/jobs/top
```

Returns top N jobs ranked by applications, views, or saves. Redis-cached for 5 minutes.

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
    { "job_id": "job_001", "count": 142 },
    { "job_id": "job_003", "count": 97 }
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

Calculates the conversion funnel for a specific job or all jobs.

**Request:**
```json
{
  "job_id": "job_001",
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
  "view_to_save_rate": 0.161,
  "save_to_apply_rate": 0.391,
  "view_to_apply_rate": 0.063
}
```

---

### 4. Geo Distribution

```
POST /analytics/geo
```

Returns city/state breakdown of job activity. Supports filtering by job, city, state, and event type.

**Request:**
```json
{
  "job_id": "job_001",
  "city": "San Jose",
  "state": "CA",
  "event_type": "application.submitted",
  "days": 30,
  "limit": 20
}
```

All fields are optional. `event_type` defaults to `["job.viewed", "application.submitted"]`.

**Response:**
```json
{
  "distribution": [
    { "location": "San Jose, CA", "count": 78 },
    { "location": "New York, NY", "count": 45 }
  ]
}
```

---

### 5. Member Dashboard

```
POST /analytics/member/dashboard
```

Returns activity metrics for a specific member.

**Request:**
```json
{ "member_id": "mem_001" }
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

---

### 6. Benchmark Report

```
POST /benchmarks/report
```

Stores a JMeter/load test result and publishes a `benchmark.completed` Kafka event.

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
    "threads": 50
  }
}
```

`scenario`: `"A"` (ingest stress test) or `"B"` (query load test)

**Response:**
```json
{ "benchmark_id": "bench_9f6ac596", "status": "stored" }
```

---

## Kafka Integration

### Broker
- **Internal (Docker):** `redpanda:9092`
- **External (localhost / EC2):** `localhost:19092`

### Topics Consumed (23 topics from all owners)

| Owner | Topics |
|---|---|
| 1 — Auth | `user.created`, `user.logout` |
| 2 — Members | `member.created`, `member.updated`, `profile.viewed` |
| 3 — Recruiters | `recruiter.created`, `recruiter.updated` |
| 4 — Jobs | `job.created`, `job.updated`, `job.closed`, `job.viewed`, `job.search.executed` |
| 5 — Applications | `application.submitted`, `application.status.updated`, `application.note.added` |
| 6 — Messaging | `message.sent`, `thread.opened`, `connection.requested`, `connection.accepted` |
| 8 — AI | `ai.requested`, `ai.completed`, `ai.approved`, `ai.rejected` |

### Topics Published

| Topic | Trigger |
|---|---|
| `analytics.<event_type>` | Every ingested event |
| `benchmark.completed` | Every benchmark report submission |

---

## Event Envelope Schema

All events follow the shared Kafka envelope agreed upon by all 8 owners:

```json
{
  "event_type": "string",
  "trace_id": "string",
  "timestamp": "ISO-8601",
  "actor_id": "string",
  "entity": {
    "entity_type": "string",
    "entity_id": "string"
  },
  "payload": {},
  "idempotency_key": "string (optional)"
}
```

---

## Performance Benchmarks

Run with JMeter via Docker:

```bash
# Run both scenarios
docker compose --profile benchmark run --rm jmeter

# Run only Scenario A (ingest stress test)
docker compose --profile benchmark run --rm -e SCENARIO=A jmeter

# Run only Scenario B (analytics query load test)
docker compose --profile benchmark run --rm -e SCENARIO=B jmeter
```

### Results (local, M-series Mac)

| Scenario | Endpoint | Threads | Requests | Throughput | Avg Latency | Error Rate |
|---|---|---|---|---|---|---|
| A — Ingest | `POST /events/ingest` | 50 | 10,000 | 186 req/s | 3ms | 0% |
| B — Queries | All analytics endpoints | 30 | 12,000 | 117 req/s | 2ms | 0% |

Results are saved to `jmeter/results/` as CSV and HTML reports.

---

## Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all 40 tests (no Docker required)
pytest tests/ -v

# Unit tests only
pytest tests/test_units.py -v

# API tests only (requires running service)
pytest tests/test_api.py -v
```

---

## Project Structure

```
owner7-analytics-service/
├── app/
│   ├── api/routes.py          # All 6 API endpoints
│   ├── config/settings.py     # Env-based config (pydantic-settings)
│   ├── consumers/
│   │   └── event_consumer.py  # aiokafka consumer (23 topics)
│   ├── models/events.py       # Pydantic models + KafkaEventEnvelope
│   ├── services/
│   │   └── analytics_service.py  # Business logic + Redis cache
│   └── utils/db.py            # MongoDB + Redis connection helpers
├── frontend/
│   ├── Dockerfile             # Multi-stage: node build → nginx serve
│   ├── nginx.conf             # Reverse proxy /analytics-api/ → FastAPI
│   └── src/
│       ├── pages/             # 10 React pages
│       ├── context/           # AuthContext (localStorage token)
│       └── config/api.js      # Service URL config
├── jmeter/
│   ├── Dockerfile             # JMeter 5.6.3 on eclipse-temurin:21
│   ├── run_tests.sh           # Entrypoint: waits for API, runs plans
│   └── plans/
│       ├── scenario_a_ingest.jmx
│       └── scenario_b_queries.jmx
├── scripts/seed_events.py     # Seed 30 days of test data
├── tests/
│   ├── test_units.py          # 40 unit tests (AsyncMock, no Docker)
│   └── test_api.py            # API integration tests
├── docker-compose.yml         # All 7 services + benchmark profile
├── Dockerfile                 # FastAPI app image
└── requirements.txt
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:19092` | Redpanda/Kafka broker |
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection |
| `MONGODB_DB` | `analytics` | Database name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `REDIS_CACHE_TTL` | `300` | Cache TTL in seconds |
| `ENV` | `development` | Environment name |

---

## Integration with Other Owners

When other owners' services are deployed on EC2, update `frontend/src/config/api.js` with their EC2 URLs:

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

Kafka: all owners point their producers/consumers to `<owner7-ec2>:19092`.
