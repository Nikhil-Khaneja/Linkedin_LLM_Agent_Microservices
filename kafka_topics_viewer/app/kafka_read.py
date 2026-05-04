"""Read-only Kafka access via kafka-python."""
from __future__ import annotations

import json
import uuid
from typing import Any

from kafka import KafkaConsumer, TopicPartition


def _decode_value(raw: bytes | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        text = raw.decode("utf-8", errors="replace")
        return {"_non_json": True, "preview": text[:8000]}


def list_topics(bootstrap: str) -> list[str]:
    c = KafkaConsumer(bootstrap_servers=[bootstrap], consumer_timeout_ms=8000)
    try:
        c.poll(timeout_ms=5000)
        return sorted(t for t in c.topics() if t and not t.startswith("__"))
    finally:
        c.close()


def tail_topic(bootstrap: str, topic: str, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 2000))
    gid = f"kafka-viewer-{uuid.uuid4().hex[:12]}"
    c = KafkaConsumer(
        bootstrap_servers=[bootstrap],
        group_id=gid,
        enable_auto_commit=False,
        consumer_timeout_ms=15000,
        value_deserializer=lambda b: _decode_value(b),
    )
    try:
        partitions = c.partitions_for_topic(topic)
        if not partitions:
            return []
        tps = [TopicPartition(topic, p) for p in sorted(partitions)]
        c.assign(tps)
        beginning = c.beginning_offsets(tps)
        end_offsets = c.end_offsets(tps)
        n_parts = len(tps)
        per = max(1, (limit + n_parts - 1) // n_parts)
        for tp in tps:
            lo, hi = beginning[tp], end_offsets[tp]
            start = max(lo, hi - per)
            c.seek(tp, start)
        out: list[dict[str, Any]] = []
        while len(out) < limit:
            polled = c.poll(timeout_ms=4000, max_records=min(500, limit * 2))
            if not polled:
                break
            batch_count = 0
            for _tp, records in polled.items():
                for msg in records:
                    batch_count += 1
                    ts = msg.timestamp
                    if ts is None or ts <= 0:
                        ts_ms = None
                    elif ts > 1_000_000_000_000:
                        ts_ms = ts
                    else:
                        ts_ms = int(ts * 1000)
                    out.append(
                        {
                            "topic": msg.topic,
                            "partition": msg.partition,
                            "offset": msg.offset,
                            "timestamp_ms": ts_ms,
                            "key": msg.key.decode("utf-8", errors="replace") if msg.key else None,
                            "value": msg.value,
                        }
                    )
            if batch_count == 0:
                break
        out.sort(key=lambda r: (r["timestamp_ms"] or 0, r["partition"], r["offset"]))
        return out[-limit:]
    finally:
        c.close()
