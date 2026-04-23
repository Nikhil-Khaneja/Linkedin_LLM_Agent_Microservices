# Owner 7 — Analytics + Kafka Host: Status Document

> Based on: `linkedin_microservices_8_ec2_accounts.pdf` spec  
> Last updated: April 25, 2026

---

## What Owner 7 Is Responsible For (per spec)

| Responsibility | Description |
|---|---|
| **Host shared Kafka broker** | All 8 owners publish/consume events through your EC2's Kafka |
| **Event ingest** | Accept events from any service via `POST /events/ingest` |
| **Dashboard rollups** | Incrementally aggregate events into recruiter + member dashboards |
| **Benchmark collection** | Store benchmark run results from all teams, publish `benchmark.completed` |
| **Final presentation artifacts** | Dashboard screenshots, benchmark charts, analytics graphs |

**Stack required by spec:** EC2 + MongoDB + Redis + Kafka

---

## Jira Tickets — Owner 7 (LI-07, LI-15, LI-23, LI-31)

### LI-07 — Week 1: Freeze event envelope + bootstrap EC2/Kafka
**Acceptance:** Kafka broker reachable by other accounts and event schema published

| Task | Status | Notes |
|---|---|---|
| Kafka event envelope schema defined | ✅ Done | `EventIngestRequest` in `app/models/events.py` — matches spec exactly |
| MongoDB collections created | ✅ Done | `events_raw`, `recruiter_dash_rollups`, `member_dash_rollups`, `benchmark_runs` |
| Redis connected and key strategy working | ✅ Done | Cache on `analytics:top_jobs:*`, `analytics:funnel:*`, `analytics:geo:*` |
| Redpanda (Kafka-compatible) running locally | ✅ Done | `docker compose up` starts it on port `19092` |
| Event schema published to team | ⚠️ Pending | Need to share the envelope format + bootstrap server address with teammates |
| EC2 bootstrap on AWS Account 7 | ⚠️ Pending | Running locally only; not deployed to EC2 yet |

---

### LI-15 — Week 2: Implement `/events/ingest` + placeholder dashboard endpoints
**Acceptance:** UI/service events are accepted and query APIs respond

| Task | Status | Notes |
|---|---|---|
| `POST /events/ingest` | ✅ Done | Validates, stores to MongoDB, republishes to Kafka `analytics.*` topic |
| `POST /analytics/jobs/top` | ✅ Done | Top N jobs by applications/views/saves with Redis cache |
| `POST /analytics/funnel` | ✅ Done | Views → saves → applications with rate calculations |
| `POST /analytics/geo` | ✅ Done | City/state distribution aggregated from events_raw |
| `POST /analytics/member/dashboard` | ✅ Done | Per-member rollup stats |
| `POST /benchmarks/report` | ✅ Done | Stores benchmark run, publishes `benchmark.completed` |
| `GET /health` | ✅ Done | Returns `{"status": "ok"}` |
| Swagger UI at `/docs` | ✅ Done | Live at `http://localhost:8000/docs` |

---

### LI-23 — Week 3: Dashboard rollups from Kafka + verify cross-account broker access
**Acceptance:** Dashboards read from event-derived rollups; cross-account Kafka access verified

| Task | Status | Notes |
|---|---|---|
| Kafka consumer subscribed to all 22 topics | ✅ Done | Subscribed to all topics from Owners 1–6, 8 |
| Idempotent event processing | ✅ Done | Duplicate `idempotency_key` check before insert |
| Rollups from `job.viewed` / `job.created` / `job.closed` | ✅ Done | Updates `recruiter_dash_rollups` |
| Rollups from `application.submitted` | ✅ Done | Updates both `recruiter_dash_rollups` and `member_dash_rollups` |
| Rollups from `application.status.updated` | ✅ Done | Tracks status transitions per member |
| Rollups from `message.sent` | ✅ Done | Increments `messages_received` for receiver |
| Rollups from `connection.accepted` | ✅ Done | Increments `connections` for both members |
| Rollups from `profile.viewed` | ✅ Done | Increments `profile_views` for viewed member |
| Rollups from `ai.*` events | ✅ Done | Tracks AI task lifecycle in `recruiter_dash_rollups` |
| Consumer retry logic with exponential backoff | ✅ Done | Max 10 retries, 2^n seconds backoff |
| Cross-account Kafka access (EC2 public DNS) | ⚠️ Pending | Not on EC2 yet; needs security group config |
| Verify teammates can connect to your broker | ⚠️ Pending | Needs EC2 deployment first |

---

### LI-31 — Week 4: Dashboard screenshots + benchmark summary exports for presentation
**Acceptance:** Presentation-ready analytics and benchmark figures exist

| Task | Status | Notes |
|---|---|---|
| Mock event generator (seed script) | ✅ Done | `scripts/seed_events.py` — simulates all 8 owners |
| 500 test events successfully ingested | ✅ Done | 100% success rate in local test |
| Unit tests for all 5 modules | ✅ Done | 40/40 passing in `tests/test_units.py` |
| Integration/API tests | ✅ Done | `tests/test_api.py` — 8 tests against live server |
| Dashboard screenshots for presentation | ⚠️ Pending | Need to capture from Redpanda Console + Swagger |
| Benchmark bar charts (Scenario A + B) | ⚠️ Pending | Need to collect runs from Owner 4 (Scenario A) and Owner 5 (Scenario B) |
| Final benchmark summary export | ⚠️ Pending | Depends on other teams submitting via `/benchmarks/report` |

---

## 6 API Endpoints — Spec vs Built

| Spec endpoint | Built | Tested |
|---|---|---|
| `POST /events/ingest` | ✅ | ✅ |
| `POST /analytics/jobs/top` | ✅ | ✅ |
| `POST /analytics/funnel` | ✅ | ✅ |
| `POST /analytics/geo` | ✅ | ✅ |
| `POST /analytics/member/dashboard` | ✅ | ✅ |
| `POST /benchmarks/report` | ✅ | ✅ |

---

## Kafka Topics — Spec vs Subscribed

| Topic | Spec producer | Subscribed in consumer |
|---|---|---|
| `user.created` | Owner 1 | ✅ |
| `user.logout` | Owner 1 | ✅ |
| `member.created` | Owner 2 | ✅ |
| `member.updated` | Owner 2 | ✅ |
| `profile.viewed` | Owner 2 | ✅ |
| `recruiter.created` | Owner 3 | ✅ |
| `recruiter.updated` | Owner 3 | ✅ |
| `job.created` | Owner 4 | ✅ |
| `job.updated` | Owner 4 | ✅ |
| `job.closed` | Owner 4 | ✅ |
| `job.viewed` | Owner 4 | ✅ |
| `job.search.executed` | Owner 4 | ✅ |
| `application.submitted` | Owner 5 | ✅ |
| `application.status.updated` | Owner 5 | ✅ |
| `application.note.added` | Owner 5 | ✅ |
| `message.sent` | Owner 6 | ✅ |
| `thread.opened` | Owner 6 | ✅ |
| `connection.requested` | Owner 6 | ✅ |
| `connection.accepted` | Owner 6 | ✅ |
| `ai.requested` | Owner 8 | ✅ |
| `ai.completed` | Owner 8 | ✅ |
| `ai.approved` | Owner 8 | ✅ |
| `ai.rejected` | Owner 8 | ✅ |

---

## MongoDB Collections — Spec vs Built

| Spec collection | Built | Indexed |
|---|---|---|
| `events_raw` | ✅ | ✅ `(event_type, timestamp)`, `idempotency_key` unique, `entity.entity_id` |
| `recruiter_dash_rollups` | ✅ | ✅ `(job_id, date)` |
| `member_dash_rollups` | ✅ | ✅ `(member_id, date)` |
| `benchmark_runs` | ✅ | ✅ `(scenario, created_at)` |

---

## What Teammates Need to Connect to Your Kafka

When you deploy to EC2, give every other owner this one line change:

```
KAFKA_BOOTSTRAP_SERVERS=<your-ec2-public-dns>:19092
```

They don't change any code — just that env var. Their existing Kafka producers/consumers will work.

**Security group rule to add on your EC2:**
- Inbound TCP port `19092` from `0.0.0.0/0` (or restrict to teammates' EC2 IPs)

---

## What's Pending — Prioritized Action List

### Immediate (before integration week)
1. **Deploy to EC2** — run `docker compose up -d` on your AWS Account 7 EC2 instance
2. **Share Kafka address** — send `<ec2-public-dns>:19092` to all 7 teammates
3. **Configure security group** — open port `19092` inbound on your EC2

### During integration week
4. **Collect benchmark runs** — ask Owner 4 to POST Scenario A results, Owner 5 for Scenario B
5. **Verify cross-account Kafka** — have one teammate connect their service and confirm events flow

### Before presentation
6. **Take dashboard screenshots** — Redpanda Console (`/topics` view) + your Swagger UI
7. **Export benchmark bar charts** — query `benchmark_runs` collection and generate charts
8. **Capture member/recruiter dashboard output** — screenshot of API responses with real data

---

## Quick Reference — Local Dev Commands

```bash
# Start everything
cd owner7-analytics-service
docker compose up -d

# Check all containers are healthy
docker ps

# Seed 500 fake events
python3 scripts/seed_events.py --count 500

# Run all unit tests (no Docker needed)
PYTHONPATH=. pytest tests/test_units.py -v

# Run integration tests (Docker must be running)
PYTHONPATH=. pytest tests/test_api.py -v

# Watch live logs
docker logs owner7-analytics-api -f

# Check what's in MongoDB
docker exec owner7-mongodb mongosh analytics --quiet \
  --eval "db.events_raw.countDocuments()"
```

**Local URLs:**
- API + Swagger: http://localhost:8000/docs
- Redpanda Console (Kafka UI): http://localhost:8080
