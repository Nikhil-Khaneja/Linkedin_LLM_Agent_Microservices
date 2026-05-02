# JMeter test plan

The project brief requires performance/scalability testing and specifically mentions graphs for:
- B
- B + S
- B + S + K
- B + S + K + Other
for 100 simultaneous user threads, and suggests Apache JMeter.

## Required scenarios from the project brief

- Scenario A: job search + job detail view
- Scenario B: apply submit (DB write + Kafka event)

## Data prerequisites

1. Seed at least 10,000 members.
2. Seed at least 10,000 job postings.
3. Seed realistic recruiter and application volume.
4. Pre-create auth tokens or create a JMeter login setup thread group.

## JMeter installation

1. Install Java 17.
2. Download Apache JMeter.
3. Start GUI with `bin/jmeter`.

## Scenario A test

Flow:
1. POST /jobs/search
2. Extract `job_id`
3. POST /jobs/get

Parameters:
- Threads: 100
- Ramp-up: 20 seconds
- Loop count: 10
- Timers: 100-300 ms random think time

Assertions:
- HTTP 200
- `success == true`
- search returns `items`
- job get returns `data.job.job_id`

## Scenario B test

Flow:
1. POST /applications/submit with unique `Idempotency-Key`
2. Optionally POST /gateway/idempotency/check for safe replay validation

Parameters:
- Threads: 100
- Ramp-up: 20 seconds
- Loop count: 5
- CSV data set: member_id, job_id, idempotency_key

Assertions:
- HTTP 200 or 409 duplicate_application depending on the dataset design
- `success == true` for normal flow

## Four benchmark configurations

1. B: no Redis, no Kafka
2. B + S: enable Redis cache for SQL-backed read paths
3. B + S + K: add Kafka async workflow
4. B + S + K + Other: add indexes, pagination tuning, pooling, or read-through cache

## Metrics to capture

- average latency
- p95 latency
- throughput (req/s)
- error rate
- CPU and memory on host

## CLI runs

```bash
jmeter -n -t tests/jmeter/scenario_a.jmx -l results/scenario_a.jtl -e -o results/scenario_a_html
jmeter -n -t tests/jmeter/scenario_b.jmx -l results/scenario_b.jtl -e -o results/scenario_b_html
```

## Charts for the presentation

Create 4-bar comparisons for average latency and throughput across the four system configurations. That is explicitly called for in the class brief.
