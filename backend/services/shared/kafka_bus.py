from __future__ import annotations
import asyncio
import json
import os
from collections import defaultdict
from typing import Any, Awaitable, Callable

from services.shared.observability import get_logger, log_event

MODE = os.environ.get("EVENT_BUS_MODE", "kafka").lower()
BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
_ALLOW_MEMORY = (os.environ.get("APP_ENV") == "test"
                 or bool(os.environ.get("PYTEST_CURRENT_TEST"))
                 or os.environ.get("ALLOW_MEMORY_CACHE") == "true")

_topics: dict[str, list[dict[str, Any]]] = defaultdict(list)
_group_offsets: dict[tuple[str, str], int] = defaultdict(int)
_topic_lock = asyncio.Lock()
_producer = None
_producer_lock = asyncio.Lock()
_logger = get_logger('event_bus')


def _serialize(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")


def _deserialize(value: bytes | None) -> Any:
    if value is None:
        return None
    return json.loads(value.decode("utf-8"))


def _ensure_mode() -> None:
    if MODE == "memory" and not _ALLOW_MEMORY:
        raise RuntimeError("EVENT_BUS_MODE=memory is test-only. Use Kafka in non-test environments.")


async def _get_producer():
    global _producer
    if MODE == 'memory':
        return None
    if _producer is not None:
        return _producer
    async with _producer_lock:
        if _producer is not None:
            return _producer
        from aiokafka import AIOKafkaProducer
        producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP, value_serializer=_serialize)
        await producer.start()
        log_event(_logger, 'kafka_producer_started', bootstrap_servers=BOOTSTRAP)
        _producer = producer
        return _producer


async def close_producer() -> None:
    global _producer
    if _producer is not None:
        try:
            await _producer.stop()
        finally:
            _producer = None


async def publish_event(topic: str, event: dict[str, Any]) -> bool:
    _ensure_mode()
    if MODE == "memory":
        async with _topic_lock:
            _topics[topic].append(event)
        return True
    try:
        producer = await _get_producer()
        await producer.send_and_wait(topic, event)
        return True
    except Exception as exc:
        log_event(_logger, 'kafka_publish_failed', topic=topic, error=str(exc))
        return False


async def consume_forever(
    topics: list[str],
    group_id: str,
    handler: Callable[[str, dict[str, Any]], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    _ensure_mode()
    if MODE == "memory":
        while not stop_event.is_set():
            next_item = None
            async with _topic_lock:
                for topic in topics:
                    offset_key = (group_id, topic)
                    offset = _group_offsets[offset_key]
                    if offset < len(_topics[topic]):
                        next_item = (topic, _topics[topic][offset])
                        _group_offsets[offset_key] = offset + 1
                        break
            if next_item is None:
                await asyncio.sleep(0.05)
                continue
            topic, payload = next_item
            await handler(topic, payload if isinstance(payload, dict) else {})
        return

    from aiokafka import AIOKafkaConsumer
    backoff = 1
    while not stop_event.is_set():
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=BOOTSTRAP,
            group_id=group_id,
            enable_auto_commit=True,
            auto_offset_reset="earliest",
            value_deserializer=_deserialize,
        )
        try:
            await consumer.start()
            log_event(_logger, 'kafka_consumer_started', topics=topics, group_id=group_id, bootstrap_servers=BOOTSTRAP)
            backoff = 1
            while not stop_event.is_set():
                batch = await consumer.getmany(timeout_ms=1000, max_records=50)
                for tp, messages in batch.items():
                    for msg in messages:
                        payload = msg.value if isinstance(msg.value, dict) else {}
                        await _handle_with_retry(tp.topic, payload, handler)
        except Exception as exc:
            log_event(_logger, 'kafka_consumer_retry', topic_list=topics, group_id=group_id, error=str(exc), backoff_seconds=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 15)
        finally:
            try:
                await consumer.stop()
            except Exception:
                pass


_HANDLER_MAX_RETRIES = 3
_HANDLER_RETRY_DELAY = 0.5


async def _handle_with_retry(
    topic: str,
    payload: dict[str, Any],
    handler: Callable[[str, dict[str, Any]], Awaitable[None]],
) -> None:
    last_exc: Exception | None = None
    for attempt in range(_HANDLER_MAX_RETRIES):
        try:
            await handler(topic, payload)
            return
        except Exception as exc:
            last_exc = exc
            log_event(_logger, 'kafka_handler_retry', topic=topic, attempt=attempt + 1, error=str(exc))
            if attempt < _HANDLER_MAX_RETRIES - 1:
                await asyncio.sleep(_HANDLER_RETRY_DELAY * (attempt + 1))
    log_event(_logger, 'kafka_handler_dlq', topic=topic, error=str(last_exc))
    await publish_event(
        f'dlq.{topic}',
        {**payload, '_dlq_source_topic': topic, '_dlq_error': str(last_exc)},
    )


def reset_memory_bus() -> None:
    _topics.clear()
    _group_offsets.clear()
