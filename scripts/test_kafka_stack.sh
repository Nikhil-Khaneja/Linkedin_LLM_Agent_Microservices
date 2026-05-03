#!/usr/bin/env bash
set -euo pipefail

TOPIC="${KAFKA_TEST_TOPIC:-kafka.test.manual}"
BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"

if command -v docker >/dev/null 2>&1; then
  docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server kafka:9092 \
    --create --if-not-exists --topic "$TOPIC" >/dev/null

  docker compose cp scripts/test_kafka_roundtrip.py auth_service:/tmp/test_kafka_roundtrip.py
  docker compose exec -T \
    -e KAFKA_TEST_TOPIC="$TOPIC" \
    -e KAFKA_BOOTSTRAP_SERVERS="kafka:9092" \
    auth_service python3 /tmp/test_kafka_roundtrip.py
else
  KAFKA_TEST_TOPIC="$TOPIC" \
  KAFKA_BOOTSTRAP_SERVERS="$BOOTSTRAP" \
  python3 scripts/test_kafka_roundtrip.py
fi
