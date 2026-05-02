#!/usr/bin/env bash
set -euo pipefail

TOPIC="${KAFKA_TEST_TOPIC:-kafka.test.manual}"
BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"

if command -v docker >/dev/null 2>&1; then
  docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server kafka:9092 \
    --create --if-not-exists --topic "$TOPIC" >/dev/null
fi

KAFKA_TEST_TOPIC="$TOPIC" \
KAFKA_BOOTSTRAP_SERVERS="$BOOTSTRAP" \
python3 scripts/test_kafka_roundtrip.py
