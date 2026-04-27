"""
test_applications.py — Pytest tests for Owner 5 Application Service.

Uses FastAPI TestClient with an in-memory SQLite database so tests run
without needing Docker / MySQL / Redis / Kafka.

Run:
    pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db
from app.models import JobStatusProjection

# ── In-memory SQLite — truly fresh on every pytest run ────────────────────────
# StaticPool ensures all sessions share the same single connection,
# which is required for SQLite in-memory databases to work with FastAPI deps.
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# ── Mock Redis out so tests never hit a live Redis instance ───────────────────
# Tests verify correctness via the MySQL UNIQUE constraint (the real safety net).
# Redis is a fast-path optimisation; its absence is handled gracefully.
import app.redis_client as _redis_mod
import app.services.application_service as _svc_mod

_no_redis = lambda: None                  # noqa: E731
_redis_mod.get_redis = _no_redis          # patch the source module
_svc_mod.get_redis   = _no_redis          # patch the already-imported reference in service


@pytest.fixture(autouse=True, scope="module")
def setup_database():
    """Create all tables fresh; seed two jobs; drop everything after module."""
    Base.metadata.drop_all(bind=test_engine)   # clean slate in case of leftovers
    Base.metadata.create_all(bind=test_engine)

    db = TestSessionLocal()
    db.merge(JobStatusProjection(job_id="job_3301", recruiter_id="rec_120", status="open"))
    db.merge(JobStatusProjection(job_id="job_3302", recruiter_id="rec_120", status="closed"))
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ── Auth header ───────────────────────────────────────────────────────────────
# Matches the default API_BEARER_TOKEN in config.py / .env.example
AUTH = {"Authorization": "Bearer owner5-demo-token"}


# ── Helper ─────────────────────────────────────────────────────────────────────

def submit_payload(job_id="job_3301", member_id="mem_t01", idem="idem-t01"):
    return {
        "job_id":          job_id,
        "member_id":       member_id,
        "resume_ref":      "s3://bucket/test.pdf",
        "idempotency_key": idem,
        "answers": [{"question_key": "auth", "answer_text": "Yes"}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — Health check
# ══════════════════════════════════════════════════════════════════════════════

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "owner5-application-service"
    assert data["status"]  == "ok"


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — Submit application to open job succeeds
# ══════════════════════════════════════════════════════════════════════════════

def test_submit_success(client):
    resp = client.post("/applications/submit", json=submit_payload(), headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["application_id"].startswith("app_")
    assert data["trace_id"].startswith("trc_")


# ══════════════════════════════════════════════════════════════════════════════
# Test 3 — Duplicate application returns HTTP 409
# ══════════════════════════════════════════════════════════════════════════════

def test_duplicate_application(client):
    # First submit succeeds
    client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_dup", idem="idem-dup-01"
    ), headers=AUTH)
    # Second submit with same job+member must return 409
    resp = client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_dup", idem="idem-dup-02"
    ), headers=AUTH)
    assert resp.status_code == 409


# ══════════════════════════════════════════════════════════════════════════════
# Test 4 — Apply to closed job returns HTTP 400
# ══════════════════════════════════════════════════════════════════════════════

def test_apply_closed_job(client):
    resp = client.post("/applications/submit", json=submit_payload(
        job_id="job_3302", member_id="mem_t02", idem="idem-closed-01"
    ), headers=AUTH)
    assert resp.status_code == 400
    assert "closed" in resp.json()["detail"].lower()


# ══════════════════════════════════════════════════════════════════════════════
# Test 5 — Get application works
# ══════════════════════════════════════════════════════════════════════════════

def test_get_application(client):
    # Submit first
    s = client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_t03", idem="idem-get-01"
    ), headers=AUTH)
    app_id = s.json()["application_id"]

    resp = client.post("/applications/get", json={"application_id": app_id}, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["application_id"] == app_id
    assert data["status"] == "submitted"
    assert len(data["answers"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Test 6 — List applications by job
# ══════════════════════════════════════════════════════════════════════════════

def test_by_job(client):
    # Submit two applications to job_3301 (new members)
    client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_byjob1", idem="idem-byjob-01"
    ), headers=AUTH)
    client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_byjob2", idem="idem-byjob-02"
    ), headers=AUTH)

    resp = client.post("/applications/byJob", json={"job_id": "job_3301"}, headers=AUTH)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 2


# ══════════════════════════════════════════════════════════════════════════════
# Test 7 — List applications by member
# ══════════════════════════════════════════════════════════════════════════════

def test_by_member(client):
    # Submit for mem_bymember to two different jobs
    client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_bymember", idem="idem-bymbr-01"
    ), headers=AUTH)
    # Add open job_3303 to projection first
    db = TestSessionLocal()
    db.merge(JobStatusProjection(job_id="job_3303", recruiter_id="rec_121", status="open"))
    db.commit()
    db.close()

    client.post("/applications/submit", json=submit_payload(
        job_id="job_3303", member_id="mem_bymember", idem="idem-bymbr-02"
    ), headers=AUTH)

    resp = client.post("/applications/byMember", json={"member_id": "mem_bymember"}, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


# ══════════════════════════════════════════════════════════════════════════════
# Test 8 — Update status works
# ══════════════════════════════════════════════════════════════════════════════

def test_update_status(client):
    s = client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_upd1", idem="idem-upd-01"
    ), headers=AUTH)
    app_id = s.json()["application_id"]

    resp = client.post("/applications/updateStatus", json={
        "application_id": app_id,
        "status":         "under_review",
        "updated_by":     "rec_120",
    }, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["old_status"] == "submitted"
    assert data["new_status"] == "under_review"


# ══════════════════════════════════════════════════════════════════════════════
# Test 9 — Invalid status returns HTTP 400
# ══════════════════════════════════════════════════════════════════════════════

def test_invalid_status(client):
    s = client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_bad1", idem="idem-bad-01"
    ), headers=AUTH)
    app_id = s.json()["application_id"]

    resp = client.post("/applications/updateStatus", json={
        "application_id": app_id,
        "status":         "dancing",
        "updated_by":     "rec_120",
    }, headers=AUTH)
    assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# Test 10 — Add recruiter note works
# ══════════════════════════════════════════════════════════════════════════════

def test_add_note(client):
    s = client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_note1", idem="idem-note-01"
    ), headers=AUTH)
    app_id = s.json()["application_id"]

    resp = client.post("/applications/addNote", json={
        "application_id": app_id,
        "recruiter_id":   "rec_120",
        "note_text":      "Strong Python background.",
    }, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "note_added"
    assert data["note_id"].startswith("note_")


# ══════════════════════════════════════════════════════════════════════════════
# Test 11 — Missing application returns HTTP 404
# ══════════════════════════════════════════════════════════════════════════════

def test_missing_application(client):
    resp = client.post("/applications/get", json={"application_id": "app_doesnotexist"}, headers=AUTH)
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Test 12 — Kafka unavailable does not crash successful DB operations
# ══════════════════════════════════════════════════════════════════════════════

def test_kafka_failure_does_not_crash(client, monkeypatch):
    """
    Simulate Kafka being unavailable.
    The submit should still succeed (DB committed) and return 201.
    """
    import app.kafka.producer as kprod

    def mock_publish(topic, envelope):
        raise Exception("Kafka unavailable — simulated failure")

    monkeypatch.setattr(kprod, "publish", mock_publish)

    resp = client.post("/applications/submit", json=submit_payload(
        job_id="job_3301", member_id="mem_kafka1", idem="idem-kafka-01"
    ), headers=AUTH)
    # DB write succeeded → 201, Kafka failure only logged
    assert resp.status_code == 201
    assert resp.json()["status"] == "submitted"
