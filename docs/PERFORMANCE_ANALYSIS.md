# Performance Analysis

**Person 4 (Sanjay) | 2026-05-02 | Section 11 — Benchmarking**

---

## 1. Caching Policy

**What is cached (Redis, TTL = 120s):**

| Cache Key | Data | Invalidated when |
|---|---|---|
| `job:search:<hash>` | Search result pages | Job updated or closed |
| `job:detail:<job_id>` | Full job document | Job updated or closed |
| `analytics:jobs:top:<hash>` | Top-N jobs by metric | New job.viewed / job.saved event |
| `analytics:funnel:<job_id>` | Funnel stage counts | New application event |
| `member:profile:<member_id>` | Member profile | Profile updated |

All services use `CACHE_MODE=redis`, `REDIS_URL=redis://redis:6379/0`. The `docker-compose.override.baseline.yml` sets `CACHE_MODE=memory` and `EVENT_BUS_MODE=memory` to disable both for config B. Cache invalidation uses `delete_pattern()` glob matching on key prefixes.

---

## 2. Messaging Flow — Why Kafka Improves Throughput

**Without Kafka (Config B):** Every request is fully synchronous. HTTP response waits for MySQL writes, cross-service calls, and analytics updates. Under 100 concurrent threads, MySQL write contention creates a bottleneck — avg latency ~160ms for apply submit.

**With Kafka outbox (Config B+S+K):** Transactional outbox pattern writes DB + outbox in one transaction, returns HTTP 202 immediately (~60ms), then background dispatcher publishes to Kafka. Analytics and notification consumers process asynchronously. HTTP thread is not blocked by downstream work.

**With 2 replicas (Config B+S+K+Other):** The `applications_service` consumer group splits Kafka partitions across both instances (partitions 0-1 → replica A, partitions 2-3 → replica B). Each message processed exactly once via idempotency key check + UNIQUE DB constraint. Throughput scales roughly linearly with replicas for write-heavy Scenario B.

---

## 3. Benchmark Results (100 threads, 20s ramp-up)

Run: `python3 scripts/run_performance_benchmarks.py --all` — stores results via `POST /benchmarks/report`, rendered as bar charts in AnalyticsPage automatically.

**Scenario A — Job Search + Detail (read-heavy)**

| Config | Avg (ms) | p50 | p95 | p99 | Req/s | Err% |
|---|---|---|---|---|---|---|
| B (baseline) | ~280 | ~240 | ~520 | ~680 | ~35 | <1% |
| B+S (+ Redis) | ~95 | ~80 | ~180 | ~240 | ~105 | <1% |
| B+S+K (+ Kafka) | ~90 | ~75 | ~170 | ~220 | ~110 | <1% |
| B+S+K+Other (+ replicas) | ~75 | ~60 | ~140 | ~190 | ~135 | <1% |

**Scenario B — Application Submit (write-heavy)**

| Config | Avg (ms) | p50 | p95 | p99 | Req/s | Err% |
|---|---|---|---|---|---|---|
| B (baseline) | ~160 | ~140 | ~320 | ~440 | ~60 | <2% |
| B+S (+ Redis) | ~140 | ~120 | ~280 | ~380 | ~68 | <2% |
| B+S+K (+ Kafka) | ~85 | ~70 | ~160 | ~210 | ~105 | <1% |
| B+S+K+Other (+ replicas) | ~60 | ~50 | ~120 | ~160 | ~155 | <1% |

**Redis hit rate** (from `GET <service>/ops/cache-stats`): rises from 0% cold to ~85% after warm-up. Stored per benchmark run as `cache_hit_rate_before`, `cache_hit_rate_after`, `cache_miss_count`.

---

## 4. Observations and Lessons

1. **Redis gives the biggest single win** — 3x throughput on Scenario A from B to B+S. For a read-heavy job platform this is the highest-leverage optimization.
2. **Kafka matters most for writes** — Scenario B latency drops 47% (B+S to B+S+K) by decoupling HTTP response from cross-service work.
3. **Horizontal scaling is additive** — 2 replicas improve Scenario B throughput ~48% over single-instance B+S+K, with Kafka consumer group partitioning ensuring no duplicate processing.
4. **Idempotency is essential** — the `idempotency_keys` MySQL table and UNIQUE `(job_id, member_id)` constraint prevent double-writes even when 100 threads share the same CSV row.
5. **Never use CACHE_MODE=memory with multiple replicas** — in-process caches are not shared across replicas, defeating the purpose entirely.
