/**
 * benchmark/apply_benchmark.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Owner 5 — Scenario B Benchmark: Apply Submit
 *
 * Measures:  avg latency, p95 latency, throughput, error rate
 * Tool:      k6  (https://k6.io)
 *
 * Install k6:
 *   brew install k6           # macOS
 *   choco install k6          # Windows
 *   sudo apt install k6       # Ubuntu
 *
 * Run — Base (no Redis, no Kafka):
 *   k6 run benchmark/apply_benchmark.js \
 *     -e API_URL=http://localhost:8005 \
 *     -e SCENARIO=base
 *
 * Run — Base + Redis (default):
 *   k6 run benchmark/apply_benchmark.js \
 *     -e API_URL=http://localhost:8005 \
 *     -e SCENARIO=redis
 *
 * Run — Base + Redis + Kafka:
 *   k6 run benchmark/apply_benchmark.js \
 *     -e API_URL=http://localhost:8005 \
 *     -e SCENARIO=kafka
 *
 * Output JSON for charts:
 *   k6 run benchmark/apply_benchmark.js --out json=benchmark_results.json
 *
 * Grading note:
 *   Run all four bar-chart scenarios (Base, B+S, B+S+K, B+S+K+Opt) and
 *   compare avg/p95 latency and req/s in the final presentation.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

// ── Custom metrics ────────────────────────────────────────────────────────────
const duplicateBlocked = new Counter("duplicate_blocked_total");
const closedJobBlocked = new Counter("closed_job_blocked_total");
const submitLatency    = new Trend("submit_latency_ms", true);
const errorRate        = new Rate("error_rate");

// ── Configuration ─────────────────────────────────────────────────────────────
const API_URL  = __ENV.API_URL  || "http://localhost:8005";
const SCENARIO = __ENV.SCENARIO || "redis";

export const options = {
  scenarios: {
    // 100 concurrent virtual users for 30 seconds
    apply_submit: {
      executor:         "constant-vus",
      vus:              100,
      duration:         "30s",
      gracefulStop:     "5s",
    },
  },
  thresholds: {
    // p95 latency must be below 2 seconds
    http_req_duration:   ["p(95)<2000"],
    // Less than 5% unexpected errors (409/400 are expected and counted separately)
    error_rate:          ["rate<0.05"],
  },
};

// ── Main VU loop ──────────────────────────────────────────────────────────────
export default function () {
  // Each VU generates a unique member_id so most submits are fresh applications.
  // A small subset intentionally duplicates to test 409 handling.
  const isDuplicate  = Math.random() < 0.10;  // 10% duplicate submissions
  const isClosedJob  = Math.random() < 0.05;  // 5% apply to closed job

  const memberId = isDuplicate
    ? "mem_bench_fixed"                        // always duplicate
    : `mem_bench_${__VU}_${Date.now()}`;

  const jobId = isClosedJob ? "job_3302" : "job_3301";

  const payload = JSON.stringify({
    job_id:          jobId,
    member_id:       memberId,
    resume_ref:      `s3://bucket/resume-${memberId}.pdf`,
    idempotency_key: `bench-${memberId}-${jobId}-${Date.now()}`,
    answers: [{ question_key: "work_auth", answer_text: "Yes" }],
  });

  const params = {
    headers: { "Content-Type": "application/json" },
    timeout: "10s",
  };

  const res = http.post(`${API_URL}/applications/submit`, payload, params);

  // ── Record latency ────────────────────────────────────────────────────────
  submitLatency.add(res.timings.duration);

  // ── Classify response ─────────────────────────────────────────────────────
  if (res.status === 201) {
    // Success
    check(res, { "submit 201": (r) => r.status === 201 });
    errorRate.add(0);

  } else if (res.status === 409) {
    // Duplicate — expected and counted separately
    duplicateBlocked.add(1);
    errorRate.add(0);  // 409 is an expected business rule, not an error

  } else if (res.status === 400) {
    // Closed job — expected
    closedJobBlocked.add(1);
    errorRate.add(0);

  } else {
    // Unexpected error (5xx etc.)
    errorRate.add(1);
    console.error(`Unexpected ${res.status}: ${res.body}`);
  }

  sleep(0.1);  // brief pause between requests per VU
}

// ── Summary report ────────────────────────────────────────────────────────────
export function handleSummary(data) {
  const scenario = SCENARIO;
  const metrics  = data.metrics;

  const summary = {
    scenario:               scenario,
    total_requests:         metrics.http_reqs?.values?.count       || 0,
    throughput_rps:         metrics.http_reqs?.values?.rate        || 0,
    avg_latency_ms:         metrics.http_req_duration?.values?.avg || 0,
    p95_latency_ms:         metrics.http_req_duration?.values["p(95)"] || 0,
    p99_latency_ms:         metrics.http_req_duration?.values["p(99)"] || 0,
    error_rate_pct:         (metrics.error_rate?.values?.rate || 0) * 100,
    duplicate_blocked:      metrics.duplicate_blocked_total?.values?.count || 0,
    closed_job_blocked:     metrics.closed_job_blocked_total?.values?.count || 0,
  };

  console.log("\n========== OWNER 5 SCENARIO B BENCHMARK RESULT ==========");
  console.log(`Scenario:            ${summary.scenario}`);
  console.log(`Total requests:      ${summary.total_requests}`);
  console.log(`Throughput (req/s):  ${summary.throughput_rps.toFixed(2)}`);
  console.log(`Avg latency:         ${summary.avg_latency_ms.toFixed(2)} ms`);
  console.log(`P95 latency:         ${summary.p95_latency_ms.toFixed(2)} ms`);
  console.log(`P99 latency:         ${summary.p99_latency_ms.toFixed(2)} ms`);
  console.log(`Error rate:          ${summary.error_rate_pct.toFixed(2)}%`);
  console.log(`Duplicate blocked:   ${summary.duplicate_blocked}`);
  console.log(`Closed job blocked:  ${summary.closed_job_blocked}`);
  console.log("==========================================================\n");

  return {
    stdout:                        JSON.stringify(summary, null, 2),
    [`benchmark_${scenario}.json`]: JSON.stringify(data, null, 2),
  };
}
