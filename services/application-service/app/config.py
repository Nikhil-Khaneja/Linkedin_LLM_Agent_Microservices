"""
config.py — All environment-based settings for Owner 5 Application Service.
Every external dependency is configurable. No hardcoded IPs or ports.
"""

import os

# ── API Auth ──────────────────────────────────────────────────────────────────
# Bearer token used to protect all /applications/* endpoints.
# In standalone demo mode the default value is used.
# In team integration, set this to a shared secret via env var.
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "owner5-demo-token")

# ── Database ──────────────────────────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "3307"))
DB_NAME     = os.getenv("DB_NAME", "application_core")
DB_USER     = os.getenv("DB_USER", "app_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "app_password")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6385"))
REDIS_IDEMPOTENCY_TTL = int(os.getenv("REDIS_IDEMPOTENCY_TTL_SECONDS", "86400"))

# ── Kafka ─────────────────────────────────────────────────────────────────────
# Owner 7 EC2 public DNS — set via env variable; do NOT hardcode.
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Topics this service produces
TOPIC_APPLICATION_SUBMITTED     = "application.submitted"
TOPIC_APPLICATION_STATUS_UPDATED = "application.status.updated"
TOPIC_APPLICATION_NOTE_ADDED    = "application.note.added"

# Topics this service consumes (from Owner 4)
TOPIC_JOB_CREATED = "job.created"
TOPIC_JOB_UPDATED = "job.updated"
TOPIC_JOB_CLOSED  = "job.closed"

# Consumer group for this service
KAFKA_CONSUMER_GROUP = "owner5-application-service"

# ── Demo / standalone mode ────────────────────────────────────────────────────
# When true, unknown job_id is allowed (stand-alone demo mode).
# Set to false in final team integration.
DEMO_ALLOW_UNKNOWN_JOB = os.getenv("DEMO_ALLOW_UNKNOWN_JOB", "true").lower() == "true"
