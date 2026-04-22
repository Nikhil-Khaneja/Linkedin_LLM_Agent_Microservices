"""
Kafka consumer that listens to ALL domain topics from Owners 1-6,8.
Processes events into MongoDB rollups idempotently.
"""
import json
import asyncio
import logging
from datetime import datetime
from aiokafka import AIOKafkaConsumer
from app.config.settings import get_settings
from app.utils.db import get_db

logger = logging.getLogger(__name__)

# All topics Owner 7 consumes from other services
SUBSCRIBED_TOPICS = [
    # Owner 1
    "user.created", "user.logout",
    # Owner 2
    "member.created", "member.updated", "profile.viewed",
    # Owner 3
    "recruiter.created", "recruiter.updated",
    # Owner 4
    "job.created", "job.updated", "job.closed", "job.viewed", "job.search.executed",
    # Owner 5
    "application.submitted", "application.status.updated", "application.note.added",
    # Owner 6
    "message.sent", "thread.opened",
    "connection.requested", "connection.accepted",
    # Owner 8
    "ai.requested", "ai.completed", "ai.approved", "ai.rejected",
]


async def start_consumer():
    """Long-running Kafka consumer task."""
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        *SUBSCRIBED_TOPICS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        enable_auto_commit=True,
    )

    retry_count = 0
    max_retries = 10

    while retry_count < max_retries:
        try:
            await consumer.start()
            logger.info(f"Kafka consumer started, subscribed to {len(SUBSCRIBED_TOPICS)} topics")
            retry_count = 0  # reset on successful connection

            async for msg in consumer:
                try:
                    await _process_event(msg.topic, msg.value)
                except Exception as e:
                    logger.error(f"Error processing event from {msg.topic}: {e}", exc_info=True)

        except Exception as e:
            retry_count += 1
            wait_time = min(2 ** retry_count, 30)
            logger.warning(f"Kafka consumer error (attempt {retry_count}): {e}. Retrying in {wait_time}s")
            await asyncio.sleep(wait_time)
        finally:
            try:
                await consumer.stop()
            except Exception:
                pass

    logger.error("Kafka consumer exhausted retries, stopping.")


async def _process_event(topic: str, event: dict):
    """
    Idempotent event processing:
    1. Check idempotency_key to avoid double-processing
    2. Store in events_raw
    3. Update relevant rollups
    """
    db = get_db()
    idem_key = event.get("idempotency_key")

    # Idempotency guard
    if idem_key:
        exists = await db.events_raw.find_one({"idempotency_key": idem_key})
        if exists:
            logger.debug(f"Skipping duplicate event: {idem_key}")
            return

    # Store raw event
    event_doc = {
        "event_id": f"evt_kafka_{event.get('trace_id', 'unknown')}",
        "event_type": topic,
        "trace_id": event.get("trace_id"),
        "timestamp": datetime.fromisoformat(event["timestamp"]) if "timestamp" in event else datetime.utcnow(),
        "actor_id": event.get("actor_id"),
        "entity": event.get("entity", {}),
        "payload": event.get("payload", {}),
        "idempotency_key": idem_key,
        "source": "kafka",
    }
    try:
        await db.events_raw.insert_one(event_doc)
    except Exception as e:
        if "duplicate key" in str(e).lower():
            return
        raise

    # Update rollups based on event type
    await _update_rollup_from_kafka(topic, event, db)
    logger.info(f"Processed Kafka event: {topic} | trace: {event.get('trace_id')}")


async def _update_rollup_from_kafka(topic: str, event: dict, db):
    """Update rollup collections based on consumed Kafka events."""
    date_key = datetime.utcnow().strftime("%Y-%m-%d")
    entity = event.get("entity", {})
    payload = event.get("payload", {})
    actor_id = event.get("actor_id")

    # ── Job-related rollups ────────────────────────────────────────
    if topic in ("job.viewed", "job.created", "job.updated", "job.closed", "job.search.executed"):
        job_id = entity.get("entity_id") if entity.get("entity_type") == "job" else payload.get("job_id")
        if job_id:
            field = topic.replace(".", "_")
            await db.recruiter_dash_rollups.update_one(
                {"job_id": job_id, "date": date_key},
                {"$inc": {field: 1}},
                upsert=True,
            )

    # ── Application rollups ────────────────────────────────────────
    elif topic == "application.submitted":
        job_id = payload.get("job_id")
        member_id = payload.get("member_id") or actor_id
        if job_id:
            await db.recruiter_dash_rollups.update_one(
                {"job_id": job_id, "date": date_key},
                {"$inc": {"application_submitted": 1}},
                upsert=True,
            )
        if member_id:
            await db.member_dash_rollups.update_one(
                {"member_id": member_id, "date": date_key},
                {"$inc": {"applications_sent": 1}},
                upsert=True,
            )

    elif topic == "application.status.updated":
        member_id = payload.get("member_id") or actor_id
        new_status = payload.get("new_status", "unknown")
        if member_id:
            await db.member_dash_rollups.update_one(
                {"member_id": member_id, "date": date_key},
                {"$inc": {f"status_{new_status}": 1}},
                upsert=True,
            )

    # ── Social rollups ─────────────────────────────────────────────
    elif topic == "message.sent":
        receiver = payload.get("receiver_id")
        if receiver:
            await db.member_dash_rollups.update_one(
                {"member_id": receiver, "date": date_key},
                {"$inc": {"messages_received": 1}},
                upsert=True,
            )

    elif topic == "connection.accepted":
        for mid in [actor_id, payload.get("receiver_id")]:
            if mid:
                await db.member_dash_rollups.update_one(
                    {"member_id": mid, "date": date_key},
                    {"$inc": {"connections": 1}},
                    upsert=True,
                )

    # ── Profile rollups ────────────────────────────────────────────
    elif topic == "profile.viewed":
        viewed_id = entity.get("entity_id")
        if viewed_id:
            await db.member_dash_rollups.update_one(
                {"member_id": viewed_id, "date": date_key},
                {"$inc": {"profile_views": 1}},
                upsert=True,
            )

    # ── AI rollups ─────────────────────────────────────────────────
    elif topic in ("ai.requested", "ai.completed", "ai.approved", "ai.rejected"):
        field = topic.replace(".", "_")
        await db.recruiter_dash_rollups.update_one(
            {"job_id": payload.get("job_id", "global"), "date": date_key},
            {"$inc": {field: 1}},
            upsert=True,
        )
