#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


BOOTSTRAP = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
TOPIC = os.environ.get('KAFKA_TEST_TOPIC', f'kafka.test.{uuid.uuid4().hex[:8]}')
GROUP_ID = os.environ.get('KAFKA_TEST_GROUP_ID', f'kafka-test-{uuid.uuid4().hex[:8]}')
TIMEOUT_SECONDS = float(os.environ.get('KAFKA_TEST_TIMEOUT_SECONDS', '20'))


def _event() -> dict:
    trace = f'trc_{uuid.uuid4()}'
    entity_id = f'app_{uuid.uuid4().hex[:8]}'
    return {
        'event_type': 'application.submitted',
        'trace_id': trace,
        'timestamp': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'actor_id': 'mem_kafka_test',
        'entity': {'entity_type': 'application', 'entity_id': entity_id},
        'payload': {
            'job_id': 'job_kafka_test',
            'member_id': 'mem_kafka_test',
            'resume_ref': 'resume-kafka-test.pdf',
            'submission_metadata': {'source': 'integration_test'},
        },
        'idempotency_key': f'application.submitted:{entity_id}:mem_kafka_test',
    }


async def main() -> int:
    event = _event()
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v, separators=(',', ':')).encode('utf-8'),
    )
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP_ID,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    )

    try:
        await producer.start()
        await consumer.start()
        await producer.send_and_wait(TOPIC, event)
        deadline = asyncio.get_running_loop().time() + TIMEOUT_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            batch = await consumer.getmany(timeout_ms=1000, max_records=10)
            for _tp, messages in batch.items():
                for msg in messages:
                    payload = msg.value or {}
                    if payload.get('trace_id') == event['trace_id']:
                        print(json.dumps({
                            'status': 'ok',
                            'bootstrap_servers': BOOTSTRAP,
                            'topic': TOPIC,
                            'group_id': GROUP_ID,
                            'event_type': payload.get('event_type'),
                            'trace_id': payload.get('trace_id'),
                            'entity_id': ((payload.get('entity') or {}).get('entity_id')),
                        }, separators=(',', ':')))
                        return 0
        print(json.dumps({
            'status': 'timeout',
            'bootstrap_servers': BOOTSTRAP,
            'topic': TOPIC,
            'group_id': GROUP_ID,
            'expected_trace_id': event['trace_id'],
        }, separators=(',', ':')), file=sys.stderr)
        return 1
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass
        try:
            await producer.stop()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
