# Observability Guide

This project separates **business analytics** from **platform observability**:

- **Owner 7 analytics** stores user and domain events for recruiter/member dashboards.
- **Prometheus + Grafana** are used for service health, latency, traffic, and cache efficiency.

## What each backend service exposes

Each service provides:
- `/ops/healthz` for liveness checks
- `/ops/cache-stats` for cache efficiency and namespace-level stats
- `/ops/metrics` for Prometheus scraping

## Structured request logs

Every service emits JSON logs with:
- timestamp
- service
- trace_id
- method
- path
- status_code
- duration_ms
- client_host

Trace IDs are propagated through:
- HTTP `X-Trace-Id`
- response bodies
- Kafka event envelopes

## Cache hit rate

Each service calculates:
- total lookups
- hits
- misses
- hit rate %
- sets
- deletes
- increments
- errors
- namespace-level hit rate breakdown

## Grafana dashboards

The repo provisions a default service overview dashboard showing:
- requests/sec by service
- p95 latency by service
- cache hit rate % by service

## How to use it locally

1. Start the full stack with `./scripts/bootstrap_local.sh`
2. Open Grafana at `http://localhost:3000`
3. Login with `admin / admin`
4. Open the `LinkedIn Clone Service Overview` dashboard

## Recommended production extensions

- ship logs to Loki or CloudWatch
- export traces to Tempo or AWS X-Ray
- add alert rules for elevated latency, dependency failures, and low cache hit rates
- add DB-specific dashboards and Kafka consumer lag dashboards
