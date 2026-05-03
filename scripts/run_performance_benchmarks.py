#!/usr/bin/env python3
"""Run concurrent HTTP benchmarks (100 threads) and persist results via analytics_service.

Person 4 (Sanjay) — benchmarks for 4 configurations:
  B          : baseline (no Redis warm cache, no Kafka async)
  B+S        : + Redis cache warmed up before run
  B+S+K      : + Kafka async outbox enabled (default stack)
  B+S+K+Other: + 2 service replicas (run with docker compose --scale)

Usage:
  # Generate a token first (run from repo root):
  python3 scripts/run_performance_benchmarks.py --config B
  python3 scripts/run_performance_benchmarks.py --config B+S
  python3 scripts/run_performance_benchmarks.py --config B+S+K
  python3 scripts/run_performance_benchmarks.py --config B+S+K+Other

  # Or run all configs in sequence:
  python3 scripts/run_performance_benchmarks.py --all
"""
import argparse
import csv
import os
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

backend_root = str((Path(__file__).resolve().parents[1] / 'backend'))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)
from services.shared.auth import issue_access_token  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
THREADS    = 100   # concurrent threads (matches JMeter plan)
LOOPS_A    = 10    # loops per thread for Scenario A
LOOPS_B    = 5     # loops per thread for Scenario B
RAMP_SECS  = 20    # ramp-up seconds (stagger thread start)

CONFIG_DESCRIPTIONS = {
    'B':            'Baseline — no Redis, no Kafka (docker-compose.override.baseline.yml)',
    'B+S':          'Base + Redis cache enabled + warmed before run',
    'B+S+K':        'Base + Redis + Kafka outbox enabled (default stack)',
    'B+S+K+Other':  'Base + Redis + Kafka + 2 replicas (--scale jobs_service=2 applications_service=2)',
}

# SETUP INSTRUCTIONS per config — run BEFORE calling this script:
#
# Config B (baseline — no Redis/Kafka):
#   docker compose -f docker-compose.yml -f docker-compose.override.baseline.yml up -d --build
#   Wait for healthy, then: python3 scripts/run_performance_benchmarks.py --config B
#
# Config B+S (Redis on, cold cache → script warms it):
#   docker compose up -d
#   python3 scripts/run_performance_benchmarks.py --config B+S
#
# Config B+S+K (full default stack):
#   docker compose up -d
#   python3 scripts/run_performance_benchmarks.py --config B+S+K
#
# Config B+S+K+Other (2 replicas):
#   docker compose up -d --scale jobs_service=2 --scale applications_service=2
#   python3 scripts/run_performance_benchmarks.py --config "B+S+K+Other"

# ---------------------------------------------------------------------------
# Core concurrent measurement
# ---------------------------------------------------------------------------

def _worker(url: str, payload: dict, headers: dict, loops: int) -> list[float]:
    """Each worker fires `loops` POST requests and returns latency list (ms)."""
    latencies = []
    sess = requests.Session()
    for _ in range(loops):
        t0 = time.perf_counter()
        try:
            resp = sess.post(url, json=payload, headers=headers, timeout=10)
            # treat 4xx/5xx as error — still record latency
            if resp.status_code >= 500:
                latencies.append(-1.0)   # sentinel for error
                continue
        except Exception:
            latencies.append(-1.0)
            continue
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


def measure_concurrent(url: str, payload: dict, headers: dict,
                        threads: int = THREADS, loops: int = LOOPS_A,
                        ramp_secs: float = RAMP_SECS) -> dict:
    """Run `threads` workers concurrently, staggered over ramp_secs."""
    all_latencies: list[float] = []
    errors = 0
    delay_per_thread = ramp_secs / max(threads, 1)

    started = time.perf_counter()
    futures = []
    with ThreadPoolExecutor(max_workers=threads) as pool:
        for i in range(threads):
            # stagger start slightly to simulate ramp-up
            time.sleep(delay_per_thread * (1 if i < threads - 1 else 0))
            futures.append(pool.submit(_worker, url, payload, headers, loops))
        for fut in as_completed(futures):
            for lat in fut.result():
                if lat < 0:
                    errors += 1
                else:
                    all_latencies.append(lat)
    total_seconds = max(time.perf_counter() - started, 0.001)
    total_requests = threads * loops

    good = [l for l in all_latencies if l >= 0]
    if not good:
        good = [0.0]

    sorted_lat = sorted(good)
    p50_idx = int(len(sorted_lat) * 0.50)
    p95_idx = int(len(sorted_lat) * 0.95)
    p99_idx = int(len(sorted_lat) * 0.99)

    return {
        'total_requests':  total_requests,
        'latency_ms_avg':  round(statistics.mean(good), 2),
        'latency_ms_p50':  round(sorted_lat[min(p50_idx, len(sorted_lat)-1)], 2),
        'latency_ms_p95':  round(sorted_lat[min(p95_idx, len(sorted_lat)-1)], 2),
        'latency_ms_p99':  round(sorted_lat[min(p99_idx, len(sorted_lat)-1)], 2),
        'throughput':      round(total_requests / total_seconds, 2),
        'error_count':     errors,
        'error_rate_pct':  round((errors / total_requests) * 100, 2),
    }


# ---------------------------------------------------------------------------
# Cache stats helper
# ---------------------------------------------------------------------------

def get_cache_stats(base_url: str, headers: dict) -> dict:
    """Fetch /ops/cache-stats from the given service base URL."""
    try:
        resp = requests.get(f'{base_url}/ops/cache-stats', headers=headers, timeout=5)
        return resp.json() if resp.status_code == 200 else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Scenario A: job search + job detail
# ---------------------------------------------------------------------------

def run_scenario_a(config: str, jobs_base: str, analytics_base: str,
                   headers: dict, job_id: str) -> list[dict]:
    print(f'\n[Scenario A] Config={config}  — {CONFIG_DESCRIPTIONS[config]}')

    # Warm cache for B+S configs
    if 'S' in config:
        print('  Warming cache ...')
        for _ in range(5):
            requests.post(f'{jobs_base}/jobs/search',
                          json={'keyword': 'Engineer', 'page_size': 20},
                          headers=headers, timeout=10)
            requests.post(f'{jobs_base}/jobs/get',
                          json={'job_id': job_id}, headers=headers, timeout=10)

    cache_before = get_cache_stats(jobs_base, headers)

    # Step 1: job search
    print('  Running /jobs/search (100 threads × 10 loops) ...')
    stats_search = measure_concurrent(
        url=f'{jobs_base}/jobs/search',
        payload={'keyword': 'Engineer', 'page_size': 20},
        headers=headers,
        threads=THREADS, loops=LOOPS_A,
    )
    print(f'    search → avg={stats_search["latency_ms_avg"]}ms  p95={stats_search["latency_ms_p95"]}ms  tput={stats_search["throughput"]}req/s')

    # Step 2: job detail
    print('  Running /jobs/get (100 threads × 10 loops) ...')
    stats_get = measure_concurrent(
        url=f'{jobs_base}/jobs/get',
        payload={'job_id': job_id},
        headers=headers,
        threads=THREADS, loops=LOOPS_A,
    )
    print(f'    get    → avg={stats_get["latency_ms_avg"]}ms  p95={stats_get["latency_ms_p95"]}ms  tput={stats_get["throughput"]}req/s')

    cache_after = get_cache_stats(jobs_base, headers)

    reports = [
        {
            'scenario': 'A-search', 'variant': config,
            'description': f'Scenario A /jobs/search — {CONFIG_DESCRIPTIONS[config]}',
            'cache_hit_rate_before': cache_before.get('hit_rate_pct', 0),
            'cache_hit_rate_after':  cache_after.get('hit_rate_pct', 0),
            'cache_miss_count':      cache_after.get('misses', 0),
            'cache_hit_count':       cache_after.get('hits', 0),
            **stats_search,
        },
        {
            'scenario': 'A-detail', 'variant': config,
            'description': f'Scenario A /jobs/get — {CONFIG_DESCRIPTIONS[config]}',
            'cache_hit_rate_before': cache_before.get('hit_rate_pct', 0),
            'cache_hit_rate_after':  cache_after.get('hit_rate_pct', 0),
            'cache_miss_count':      cache_after.get('misses', 0),
            'cache_hit_count':       cache_after.get('hits', 0),
            **stats_get,
        },
    ]
    return reports


# ---------------------------------------------------------------------------
# Scenario B: application submit
# ---------------------------------------------------------------------------

def run_scenario_b(config: str, app_base: str, analytics_base: str,
                   headers: dict, csv_path: str) -> list[dict]:
    print(f'\n[Scenario B] Config={config}  — {CONFIG_DESCRIPTIONS[config]}')

    # Load CSV rows for member_id + job_id pairs
    rows: list[dict] = []
    if Path(csv_path).exists():
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
    else:
        # fallback synthetic rows
        rows = [
            {'member_id': f'mem_seed_{i:05d}',
             'job_id':    f'job_seed_{(i % 200)+1:05d}',
             'idempotency_key': uuid.uuid4().hex}
            for i in range(1, 501)
        ]

    cache_before = get_cache_stats(app_base, headers)

    def worker_b(loops: int) -> list[float]:
        latencies = []
        sess = requests.Session()
        for _ in range(loops):
            row = rows[int(time.time() * 1000) % len(rows)]
            idem_key = uuid.uuid4().hex   # fresh key each attempt to avoid 409 masking real failures
            hdrs = {**headers, 'Idempotency-Key': idem_key}
            t0 = time.perf_counter()
            try:
                resp = sess.post(
                    f'{app_base}/applications/submit',
                    json={'member_id': row['member_id'], 'job_id': row['job_id'],
                          'resume_ref': 'seed_resume.pdf',
                          'cover_letter': 'Benchmark test submission'},
                    headers=hdrs, timeout=10,
                )
                if resp.status_code >= 500:
                    latencies.append(-1.0)
                    continue
            except Exception:
                latencies.append(-1.0)
                continue
            latencies.append((time.perf_counter() - t0) * 1000)
        return latencies

    print('  Running /applications/submit (100 threads × 5 loops) ...')
    all_latencies: list[float] = []
    errors = 0
    ramp_delay = RAMP_SECS / THREADS
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futures = [pool.submit(worker_b, LOOPS_B) for _ in range(THREADS)]
        for i, fut in enumerate(futures):
            time.sleep(ramp_delay * (1 if i < THREADS - 1 else 0))
        for fut in as_completed(futures):
            for lat in fut.result():
                if lat < 0:
                    errors += 1
                else:
                    all_latencies.append(lat)
    total_seconds = max(time.perf_counter() - started, 0.001)
    total_requests = THREADS * LOOPS_B

    good = sorted(all_latencies) if all_latencies else [0.0]
    stats = {
        'total_requests':  total_requests,
        'latency_ms_avg':  round(statistics.mean(good), 2),
        'latency_ms_p50':  round(good[int(len(good)*0.50)], 2),
        'latency_ms_p95':  round(good[min(int(len(good)*0.95), len(good)-1)], 2),
        'latency_ms_p99':  round(good[min(int(len(good)*0.99), len(good)-1)], 2),
        'throughput':      round(total_requests / total_seconds, 2),
        'error_count':     errors,
        'error_rate_pct':  round((errors / total_requests) * 100, 2),
    }
    print(f'    submit → avg={stats["latency_ms_avg"]}ms  p95={stats["latency_ms_p95"]}ms  tput={stats["throughput"]}req/s')

    cache_after = get_cache_stats(app_base, headers)

    return [{
        'scenario': 'B-submit', 'variant': config,
        'description': f'Scenario B /applications/submit — {CONFIG_DESCRIPTIONS[config]}',
        'cache_hit_rate_before': cache_before.get('hit_rate_pct', 0),
        'cache_hit_rate_after':  cache_after.get('hit_rate_pct', 0),
        'cache_miss_count':      cache_after.get('misses', 0),
        'cache_hit_count':       cache_after.get('hits', 0),
        **stats,
    }]


# ---------------------------------------------------------------------------
# Store results
# ---------------------------------------------------------------------------

def store_report(report: dict, analytics_base: str, headers: dict) -> None:
    try:
        resp = requests.post(f'{analytics_base}/benchmarks/report',
                             json=report, headers=headers, timeout=10)
        resp.raise_for_status()
        bid = resp.json().get('data', {}).get('benchmark_id', '?')
        print(f'    ✓ stored benchmark_id={bid}')
    except Exception as e:
        print(f'    ✗ failed to store: {e}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Person 4 — concurrent benchmark runner (100 threads)')
    parser.add_argument('--config', choices=list(CONFIG_DESCRIPTIONS.keys()),
                        help='Single config to run')
    parser.add_argument('--all', action='store_true',
                        help='Run all 4 configs in sequence')
    parser.add_argument('--analytics-base', default='http://localhost:8007')
    parser.add_argument('--jobs-base',       default='http://localhost:8004')
    parser.add_argument('--app-base',        default='http://localhost:8005')
    parser.add_argument('--job-id',          default='job_seed_00001')
    parser.add_argument('--csv',
                        default='tests/jmeter/scenario_b_data.csv',
                        help='CSV file with member_id,job_id,idempotency_key columns')
    args = parser.parse_args()

    if not args.all and not args.config:
        parser.error('Provide --config <name> or --all')

    configs_to_run = list(CONFIG_DESCRIPTIONS.keys()) if args.all else [args.config]

    token = issue_access_token(sub='adm_1', role='admin', email='admin@example.com')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    all_reports: list[dict] = []
    # track throughput per config for comparison summary
    throughput_summary: dict[str, list[float]] = {}

    for config in configs_to_run:
        print(f'\n{"="*60}')
        print(f'CONFIG: {config}')
        print(f'{"="*60}')

        reports_a = run_scenario_a(config, args.jobs_base, args.analytics_base,
                                   headers, args.job_id)
        reports_b = run_scenario_b(config, args.app_base, args.analytics_base,
                                   headers, args.csv)

        config_reports = reports_a + reports_b
        throughput_summary[config] = [r.get('throughput', 0) for r in config_reports]

        for report in config_reports:
            store_report(report, args.analytics_base, headers)
            all_reports.append(report)

    # Print throughput improvement table (multi-replica vs single-replica baseline)
    print(f'\n{"="*60}')
    print('THROUGHPUT COMPARISON (req/s):')
    print(f'{"Config":<18} {"Avg throughput":>16} {"vs B+S+K baseline":>20}')
    print('-' * 58)
    baseline_tput = statistics.mean(throughput_summary.get('B+S+K', [1])) or 1
    for cfg, tputs in throughput_summary.items():
        avg = round(statistics.mean(tputs), 1) if tputs else 0
        improvement = f'+{round((avg/baseline_tput - 1)*100, 1)}%' if cfg != 'B+S+K' else 'baseline'
        print(f'{cfg:<18} {avg:>16.1f} {improvement:>20}')

    print(f'\nDONE — stored {len(all_reports)} benchmark reports.')
    print('Open AnalyticsPage in the frontend to see the bar charts.')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
