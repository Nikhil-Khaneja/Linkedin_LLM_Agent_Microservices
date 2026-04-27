"""
PHASE 5 — Kafka Service Communication Example (AUTOMATED BY AI)

Demonstrates the canonical pattern used in this project:

  job-service (owner4)  →  publishes  job.events / application.events
  application-service (owner5)  →  consumes application.events
  analytics-service (owner7)    →  consumes all events

Run standalone to test:
    pip install aiokafka
    KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python order_to_payment_example.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.kafka_utils import Event, KafkaTopics, publish, consume, stop_producer


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCER SIDE — job-service (owner4)
# Paste this pattern into services/job-service/app/services/job_publisher.py
# ─────────────────────────────────────────────────────────────────────────────

async def publish_job_posted(job_id: str, title: str, recruiter_id: str):
    """Called after a job is successfully saved to MySQL."""
    event = Event(
        topic=KafkaTopics.JOB_EVENTS,
        event_type="job.posted",
        source_service="job-service",
        payload={
            "job_id": job_id,
            "title": title,
            "recruiter_id": recruiter_id,
        },
    )
    await publish(event)


async def publish_application_submitted(application_id: str, job_id: str, member_id: str):
    """Called by application-service after insert."""
    event = Event(
        topic=KafkaTopics.APPLICATION_EVENTS,
        event_type="application.submitted",
        source_service="application-service",
        payload={
            "application_id": application_id,
            "job_id": job_id,
            "member_id": member_id,
        },
    )
    await publish(event)


# ─────────────────────────────────────────────────────────────────────────────
# CONSUMER SIDE — analytics-service (owner7)
# Paste into services/analytics-service/app/consumers/event_consumer.py
# ─────────────────────────────────────────────────────────────────────────────

async def analytics_event_handler(event: Event):
    """analytics-service handler: persists all events to MongoDB."""
    print(f"[analytics] received {event.event_type} from {event.source_service}")
    # In the real service:
    #   db = get_mongo_db()
    #   await db.events.insert_one(asdict(event))


async def start_analytics_consumer():
    await consume(
        topics=[KafkaTopics.JOB_EVENTS, KafkaTopics.APPLICATION_EVENTS, KafkaTopics.MEMBER_EVENTS],
        group_id="analytics-consumer-group",
        handler=analytics_event_handler,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CONSUMER SIDE — notification-service (future)
# ─────────────────────────────────────────────────────────────────────────────

async def notification_event_handler(event: Event):
    """Sends email/push when application.submitted fires."""
    if event.event_type == "application.submitted":
        print(f"[notification] Sending confirmation to member {event.payload.get('member_id')}")
        # send_email(event.payload["member_id"], "Application received!")


# ─────────────────────────────────────────────────────────────────────────────
# Demo runner
# ─────────────────────────────────────────────────────────────────────────────

async def demo():
    print("Starting consumers in background...")
    consumer_task = asyncio.create_task(start_analytics_consumer())

    await asyncio.sleep(2)   # let consumer connect

    print("Publishing events...")
    await publish_job_posted("job-001", "Senior Engineer", "recruiter-42")
    await publish_application_submitted("app-001", "job-001", "member-99")

    await asyncio.sleep(3)   # let consumer process
    consumer_task.cancel()
    await stop_producer()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(demo())
