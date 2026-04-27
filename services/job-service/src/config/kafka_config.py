"""
Kafka configuration and producer for publishing job events
"""
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from kafka import KafkaProducer
from kafka.errors import KafkaError

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Kafka producer instance
kafka_producer: Optional[KafkaProducer] = None


def init_kafka_producer():
    """Initialize Kafka producer"""
    global kafka_producer
    try:
        kafka_producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',
            retries=3,
            max_in_flight_requests_per_connection=1
        )
        logger.info(f"Kafka producer initialized: {settings.kafka_bootstrap_servers}")
    except Exception as e:
        logger.warning(f"Failed to initialize Kafka producer: {e}")
        kafka_producer = None


def close_kafka_producer():
    """Close Kafka producer"""
    global kafka_producer
    if kafka_producer:
        kafka_producer.close()
        logger.info("Kafka producer closed")


class JobEventProducer:
    """Producer for job-related Kafka events"""

    # Topic names
    TOPIC_JOB_CREATED = "job.created"
    TOPIC_JOB_UPDATED = "job.updated"
    TOPIC_JOB_CLOSED = "job.closed"
    TOPIC_JOB_VIEWED = "job.viewed"
    TOPIC_JOB_SAVED = "job.saved"
    TOPIC_JOB_SEARCH = "job.search.executed"

    def __init__(self):
        self.producer = kafka_producer

    def _create_event(
        self,
        event_type: str,
        job_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create standard Kafka event envelope"""
        return {
            "event_type": event_type,
            "trace_id": trace_id or str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor_id": actor_id,
            "entity": {
                "entity_type": "job",
                "entity_id": job_id
            },
            "payload": payload,
            "idempotency_key": idempotency_key or f"{event_type}_{job_id}_{int(datetime.utcnow().timestamp())}"
        }

    async def publish(
        self,
        topic: str,
        event_type: str,
        job_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Optional[str]:
        """Publish event to Kafka topic"""
        if not self.producer:
            logger.warning(f"Kafka producer not available, skipping event: {event_type}")
            return None

        event = self._create_event(
            event_type=event_type,
            job_id=job_id,
            actor_id=actor_id,
            payload=payload,
            trace_id=trace_id,
            idempotency_key=idempotency_key
        )

        try:
            future = self.producer.send(
                topic,
                key=job_id,
                value=event
            )
            # Wait for send to complete (with timeout)
            future.get(timeout=10)
            logger.info(f"Published event {event_type} for job {job_id}")
            return event["trace_id"]
        except KafkaError as e:
            logger.error(f"Failed to publish event {event_type}: {e}")
            # Store failed event for retry queue (future enhancement)
            return None

    async def publish_job_created(
        self,
        job_id: str,
        recruiter_id: str,
        job_data: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> Optional[str]:
        """Publish job.created event"""
        return await self.publish(
            topic=self.TOPIC_JOB_CREATED,
            event_type="job.created",
            job_id=job_id,
            actor_id=recruiter_id,
            payload=job_data,
            trace_id=trace_id
        )

    async def publish_job_updated(
        self,
        job_id: str,
        recruiter_id: str,
        updated_fields: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> Optional[str]:
        """Publish job.updated event"""
        return await self.publish(
            topic=self.TOPIC_JOB_UPDATED,
            event_type="job.updated",
            job_id=job_id,
            actor_id=recruiter_id,
            payload=updated_fields,
            trace_id=trace_id
        )

    async def publish_job_closed(
        self,
        job_id: str,
        recruiter_id: str,
        reason: str = "",
        trace_id: Optional[str] = None
    ) -> Optional[str]:
        """Publish job.closed event - CRITICAL for Owner 5"""
        return await self.publish(
            topic=self.TOPIC_JOB_CLOSED,
            event_type="job.closed",
            job_id=job_id,
            actor_id=recruiter_id,
            payload={"reason": reason, "closed_at": datetime.utcnow().isoformat()},
            trace_id=trace_id
        )

    async def publish_job_viewed(
        self,
        job_id: str,
        viewer_id: str,
        viewer_type: str = "member",
        trace_id: Optional[str] = None
    ) -> Optional[str]:
        """Publish job.viewed event for analytics"""
        return await self.publish(
            topic=self.TOPIC_JOB_VIEWED,
            event_type="job.viewed",
            job_id=job_id,
            actor_id=viewer_id,
            payload={"viewer_type": viewer_type},
            trace_id=trace_id
        )

    async def publish_job_saved(
        self,
        job_id: str,
        member_id: str,
        trace_id: Optional[str] = None
    ) -> Optional[str]:
        """Publish job.saved event"""
        return await self.publish(
            topic=self.TOPIC_JOB_SAVED,
            event_type="job.saved",
            job_id=job_id,
            actor_id=member_id,
            payload={},
            trace_id=trace_id
        )


# Global event producer instance
event_producer: Optional[JobEventProducer] = None


def get_event_producer() -> JobEventProducer:
    """Get event producer instance"""
    global event_producer
    if event_producer is None:
        event_producer = JobEventProducer()
    return event_producer
