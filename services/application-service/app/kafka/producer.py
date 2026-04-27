"""
producer.py — Kafka producer for Owner 5 Application Service.

Publishes events for:
  - application.submitted
  - application.status.updated
  - application.note.added

Kafka failure NEVER crashes the API after a successful DB commit.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import KAFKA_BOOTSTRAP_SERVERS

logger = logging.getLogger(__name__)

# Lazy-import kafka-python so the app still starts if the package is missing
_producer = None


def _get_producer():
    """Return a shared KafkaProducer, or None if Kafka is unavailable."""
    global _producer
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer  # type: ignore
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
            request_timeout_ms=5000,
            connections_max_idle_ms=10000,
        )
        logger.info("Kafka producer connected to %s", KAFKA_BOOTSTRAP_SERVERS)
        return _producer
    except Exception as exc:
        logger.warning("Kafka producer unavailable: %s — events will be skipped", exc)
        return None


def _build_envelope(
    event_type: str,
    actor_id: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
    idempotency_key: str,
    trace_id: str,
) -> dict:
    """Build the standard Kafka event envelope required by the project spec."""
    return {
        "event_type":      event_type,
        "event_id":        f"evt_{uuid.uuid4().hex[:12]}",
        "trace_id":        trace_id,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "actor_id":        actor_id,
        "entity": {
            "entity_type": entity_type,
            "entity_id":   entity_id,
        },
        "payload":         payload,
        "idempotency_key": idempotency_key,
    }


def publish(topic: str, envelope: dict):
    """Send one message to Kafka. Silently logs on failure."""
    producer = _get_producer()
    if producer is None:
        logger.warning("Kafka unavailable — skipping publish to %s", topic)
        return
    try:
        future = producer.send(topic, value=envelope)
        producer.flush(timeout=5)
        logger.info("Published to %s: %s", topic, envelope.get("event_type"))
    except Exception as exc:
        logger.error("Failed to publish to %s: %s", topic, exc)


# ── Convenience helpers ────────────────────────────────────────────────────────

def publish_application_submitted(
    application_id: str,
    job_id: str,
    member_id: str,
    resume_ref: Optional[str],
    idempotency_key: str,
    trace_id: str,
):
    envelope = _build_envelope(
        event_type      = "application.submitted",
        actor_id        = member_id,
        entity_type     = "application",
        entity_id       = application_id,
        payload         = {"job_id": job_id, "member_id": member_id, "resume_ref": resume_ref},
        idempotency_key = idempotency_key,
        trace_id        = trace_id,
    )
    publish("application.submitted", envelope)


def publish_status_updated(
    application_id: str,
    old_status: str,
    new_status: str,
    updated_by: str,
    trace_id: str,
):
    envelope = _build_envelope(
        event_type      = "application.status.updated",
        actor_id        = updated_by,
        entity_type     = "application",
        entity_id       = application_id,
        payload         = {"old_status": old_status, "new_status": new_status},
        idempotency_key = f"{application_id}-status-{new_status}",
        trace_id        = trace_id,
    )
    publish("application.status.updated", envelope)


def publish_note_added(
    application_id: str,
    note_id: str,
    recruiter_id: str,
    trace_id: str,
):
    envelope = _build_envelope(
        event_type      = "application.note.added",
        actor_id        = recruiter_id,
        entity_type     = "application",
        entity_id       = application_id,
        payload         = {"note_id": note_id, "recruiter_id": recruiter_id},
        idempotency_key = note_id,
        trace_id        = trace_id,
    )
    publish("application.note.added", envelope)
