"""
PHASE 5 — Shared Kafka utilities (AUTOMATED BY AI)
Copy this file into any Python service that needs to produce/consume events.

Usage:
    from shared.kafka_utils import get_producer, get_consumer, KafkaTopics
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


class KafkaTopics:
    JOB_EVENTS         = "job.events"
    APPLICATION_EVENTS = "application.events"
    MEMBER_EVENTS      = "member.events"
    ANALYTICS_EVENTS   = "analytics.events"
    NOTIFICATION       = "notification.events"
    BENCHMARK          = "benchmark.completed"


@dataclass
class Event:
    topic: str
    event_type: str
    payload: Dict[str, Any]
    source_service: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_bytes(self) -> bytes:
        return json.dumps(asdict(self)).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Event":
        return cls(**json.loads(data))


_producer: Optional[AIOKafkaProducer] = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
        await _producer.start()
        logger.info("Kafka producer started: %s", KAFKA_BOOTSTRAP)
    return _producer


async def stop_producer():
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


async def publish(event: Event):
    producer = await get_producer()
    await producer.send_and_wait(event.topic, event.to_bytes())
    logger.info("Published %s → %s", event.event_type, event.topic)


async def consume(
    topics: list[str],
    group_id: str,
    handler: Callable[[Event], Any],
    *,
    auto_offset_reset: str = "earliest",
):
    """
    Background consumer loop. Call from an asyncio.create_task().
    handler receives a fully-deserialized Event.
    """
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
    )
    await consumer.start()
    logger.info("Kafka consumer started: topics=%s group=%s", topics, group_id)
    try:
        async for msg in consumer:
            try:
                event = Event.from_bytes(msg.value)
                await handler(event)
            except Exception as e:
                logger.exception("Error handling event from %s: %s", msg.topic, e)
    finally:
        await consumer.stop()
