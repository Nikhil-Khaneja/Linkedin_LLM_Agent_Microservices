# Owner 9 Frontend + JMeter Runbook

Owner 9 owns the shared React frontend and performance verification.

## Owner 9 responsibilities

- deploy the shared frontend
- configure all public backend base URLs
- execute JMeter benchmark scenarios
- collect Grafana screenshots for ops metrics
- upload benchmark results through Owner 7 `/benchmarks/report`

## Frontend deployment ownership

The frontend is deployed once, separately from the backend owner services.
Recommended hosts:
- S3 + CloudFront
- Vercel / Netlify for demo
- EC2 + Nginx for strict AWS-only demo

## Required env vars

Create `.env.production` with:
- `VITE_OWNER1_URL`
- `VITE_OWNER2_URL`
- `VITE_OWNER3_URL`
- `VITE_OWNER4_URL`
- `VITE_OWNER5_URL`
- `VITE_OWNER6_URL`
- `VITE_OWNER7_URL`
- `VITE_OWNER8_URL`

## JMeter scenarios

### Scenario A
- `POST /jobs/search`
- `POST /jobs/get`

### Scenario B
- `POST /applications/submit`
- validate event dispatch path and Owner 7 analytics ingestion

## Benchmark comparison matrix

Run and compare:
- B
- B + S
- B + S + K
- B + S + K + O

Where:
- B = baseline
- S = Redis caching enabled
- K = Kafka event flow enabled
- O = indexing / request optimizations

## Evidence package for demo

Collect:
- JMeter summaries
- latency and throughput charts
- Owner 7 benchmark records
- Grafana cache hit rate charts
- Grafana p95 latency chart
