"""
Basic API endpoint tests — run with: pytest tests/test_api.py -v
Requires the service to be running (docker compose up).
"""
import pytest
import httpx

BASE = "http://localhost:8000"


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE, timeout=10.0)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ingest_event(client):
    payload = {
        "event_type": "job.viewed",
        "actor_id": "mem_101",
        "entity": {"entity_type": "job", "entity_id": "job_3001"},
        "payload": {"location": "San Jose, CA"},
    }
    r = client.post("/events/ingest", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["accepted"] is True
    assert data["event_id"].startswith("evt_")


def test_ingest_idempotent(client):
    import uuid
    payload = {
        "event_type": "job.viewed",
        "actor_id": "mem_102",
        "entity": {"entity_type": "job", "entity_id": "job_3002"},
        "idempotency_key": f"test-idem-{uuid.uuid4().hex[:8]}",
        "payload": {},
    }
    r1 = client.post("/events/ingest", json=payload)
    assert r1.status_code == 200
    original_event_id = r1.json()["event_id"]

    # Second identical request must return 409
    r2 = client.post("/events/ingest", json=payload)
    assert r2.status_code == 409
    assert r2.json()["detail"]["original_event_id"] == original_event_id


def test_top_jobs(client):
    r = client.post("/analytics/jobs/top", json={"metric": "applications", "limit": 5, "days": 30})
    assert r.status_code == 200
    assert "jobs" in r.json()


def test_funnel(client):
    r = client.post("/analytics/funnel", json={"days": 30})
    assert r.status_code == 200
    data = r.json()
    assert "views" in data
    assert "applications" in data


def test_geo(client):
    r = client.post("/analytics/geo", json={"days": 30})
    assert r.status_code == 200
    assert "distribution" in r.json()


def test_member_dashboard(client):
    r = client.post("/analytics/member/dashboard", json={"member_id": "mem_101"})
    assert r.status_code == 200
    data = r.json()
    assert "profile_views" in data
    assert "applications_sent" in data


def test_benchmark_report(client):
    payload = {
        "scenario": "A",
        "owner_id": "owner4",
        "service_name": "job-service",
        "results": {
            "base_latency_p50_ms": 45,
            "base_latency_p99_ms": 120,
            "cached_latency_p50_ms": 8,
            "cached_latency_p99_ms": 22,
            "throughput_rps": 350,
        },
        "metadata": {"dataset_size": 10000},
    }
    r = client.post("/benchmarks/report", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["benchmark_id"].startswith("bench_")
    assert data["status"] == "stored"
