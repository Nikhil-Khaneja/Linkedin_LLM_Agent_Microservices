"""
job_consumer.py — Kafka consumer for Owner 5 Application Service.

Consumes Owner 4 job lifecycle events:
  - job.created
  - job.updated
  - job.closed

Updates the local job_status_projection table so Owner 5 can check
if a job is open or closed without calling Owner 4 directly.

Run standalone:
    python -m app.kafka.job_consumer
"""

import json
import logging
import sys

from app.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    TOPIC_JOB_CREATED,
    TOPIC_JOB_UPDATED,
    TOPIC_JOB_CLOSED,
)
from app.db import SessionLocal
from app.models import JobStatusProjection, ConsumedKafkaEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [job_consumer] %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


def upsert_job_projection(db, event_data: dict):
    """Upsert job_status_projection from incoming event payload."""
    payload      = event_data.get("payload", {})
    entity       = event_data.get("entity", {})
    event_type   = event_data.get("event_type", "")
    event_id     = event_data.get("event_id", "")

    job_id       = payload.get("job_id") or entity.get("entity_id")
    recruiter_id = payload.get("recruiter_id")

    # Determine status from payload or derive from event_type
    status = payload.get("status")
    if not status:
        if event_type == "job.closed":
            status = "closed"
        else:
            status = "open"

    if not job_id:
        logger.warning("Received job event with no job_id — skipping")
        return

    # ── Idempotency check ────────────────────────────────────────────────────
    if event_id:
        existing = db.query(ConsumedKafkaEvent).filter_by(event_id=event_id).first()
        if existing:
            logger.info("Event %s already processed — skipping", event_id)
            return

    # ── Upsert job_status_projection ─────────────────────────────────────────
    row = db.query(JobStatusProjection).filter_by(job_id=job_id).first()
    if row:
        row.status = status
        if recruiter_id:
            row.recruiter_id = recruiter_id
    else:
        row = JobStatusProjection(
            job_id=job_id,
            recruiter_id=recruiter_id,
            status=status,
        )
        db.add(row)

    # ── Mark event as consumed ────────────────────────────────────────────────
    if event_id:
        db.add(ConsumedKafkaEvent(event_id=event_id, event_type=event_type))

    db.commit()
    logger.info("Upserted job_status_projection: job_id=%s status=%s", job_id, status)


def run():
    """Start the Kafka consumer loop. Runs until interrupted."""
    try:
        from kafka import KafkaConsumer  # type: ignore
    except ImportError:
        logger.error("kafka-python not installed. Run: pip install kafka-python")
        sys.exit(1)

    topics = [TOPIC_JOB_CREATED, TOPIC_JOB_UPDATED, TOPIC_JOB_CLOSED]

    try:
        consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            group_id=KAFKA_CONSUMER_GROUP,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        logger.info("Consumer listening on topics: %s", topics)
    except Exception as exc:
        logger.error("Kafka unavailable: %s — consumer will not start", exc)
        return

    db = SessionLocal()
    try:
        for message in consumer:
            try:
                event_data = message.value
                event_type = event_data.get("event_type", "unknown")
                logger.info("Received event: %s from topic: %s", event_type, message.topic)
                upsert_job_projection(db, event_data)
            except Exception as exc:
                logger.error("Error processing message: %s", exc)
                db.rollback()
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user.")
    finally:
        db.close()
        consumer.close()


if __name__ == "__main__":
    run()
