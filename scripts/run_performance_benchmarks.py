#!/usr/bin/env python3
"""Run live HTTP benchmarks and persist them via analytics_service.

This replaces the old hardcoded frontend benchmark table with measured values.
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

import requests

backend_root = str((Path(__file__).resolve().parents[1] / 'backend'))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)
from services.shared.auth import issue_access_token  # noqa: E402


def measure(url: str, payload: dict, headers: dict, runs: int) -> dict:
    latencies = []
    errors = 0
    started = time.perf_counter()
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code >= 400:
                errors += 1
        except Exception:
            errors += 1
        latencies.append((time.perf_counter() - t0) * 1000)
    total_seconds = max(time.perf_counter() - started, 0.001)
    return {
        'latency_ms_avg': round(statistics.mean(latencies), 2),
        'latency_ms_p95': round(sorted(latencies)[int(max(0, (len(latencies) * 0.95) - 1))], 2),
        'throughput': round(runs / total_seconds, 2),
        'error_rate_pct': round((errors / runs) * 100, 2),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=25)
    parser.add_argument('--analytics-base', default='http://localhost:8007')
    parser.add_argument('--jobs-base', default='http://localhost:8004')
    parser.add_argument('--job-id', default='job_seed_00001')
    args = parser.parse_args()

    token = issue_access_token(sub='adm_1', role='admin', email='admin@example.com')
    headers = {'Authorization': f'Bearer {token}'}
    scenarios = [
        ('B', 'Baseline direct jobs search', {'keyword': 'Seed', 'page_size': 20}),
        ('B+S', 'Warm-cache jobs search', {'keyword': 'Seed', 'page_size': 20}),
        ('B+S+K', 'Job detail with Kafka view event', {'job_id': args.job_id}),
        ('B+S+K+OPT', 'Funnel analytics query after warmup', {'job_id': args.job_id}),
    ]
    urls = {
        'B': f'{args.jobs_base}/jobs/search',
        'B+S': f'{args.jobs_base}/jobs/search',
        'B+S+K': f'{args.jobs_base}/jobs/get',
        'B+S+K+OPT': f'{args.analytics_base}/analytics/funnel',
    }
    reports = []
    # warm cache for B+S and optimized
    requests.post(f'{args.jobs_base}/jobs/search', json={'keyword': 'Seed', 'page_size': 20}, headers=headers, timeout=10)
    requests.post(f'{args.analytics_base}/analytics/funnel', json={'job_id': args.job_id}, headers=headers, timeout=10)
    for variant, description, payload in scenarios:
        stats = measure(urls[variant], payload, headers, args.runs)
        report = {'scenario': variant, 'variant': variant, 'description': description, **stats}
        resp = requests.post(f'{args.analytics_base}/benchmarks/report', json=report, headers=headers, timeout=10)
        resp.raise_for_status()
        reports.append(report)
        print(report)
    print(f'Reported {len(reports)} benchmark runs to analytics service.')


if __name__ == '__main__':
    main()
