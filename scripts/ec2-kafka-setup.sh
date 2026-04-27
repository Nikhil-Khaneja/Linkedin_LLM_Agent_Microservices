#!/usr/bin/env bash
# =============================================================================
# PHASE 4 — Central Kafka EC2 Setup (AUTOMATED BY AI)
# =============================================================================
# Run on the CENTRAL (owner7) EC2 instance to bring up Kafka + Zookeeper.
# This is the shared broker that all other services connect to.
#
# MANUAL STEPS REQUIRED:
#   - After running, open EC2 Security Group inbound port 9092 (or 9093 for TLS)
#   - Replace PUBLIC_IP below with this instance's actual public IP/DNS
#
# Usage: bash ec2-kafka-setup.sh <PUBLIC_IP_OR_DNS>
# =============================================================================

set -euo pipefail

PUBLIC_ADDR="${1:?Usage: $0 <EC2_PUBLIC_IP_OR_DNS>}"

# ── Install Docker ────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  if command -v apt-get &>/dev/null; then
    apt-get update -y && apt-get install -y docker.io docker-compose-plugin curl
    systemctl enable --now docker
  else
    yum update -y && yum install -y docker curl
    systemctl enable --now docker
    # docker-compose on Amazon Linux
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
      -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
  fi
fi

mkdir -p /opt/linkedin/kafka
cd /opt/linkedin/kafka

# ── Write docker-compose for Kafka ───────────────────────────────────────────
cat > docker-compose.yml <<COMPOSE
version: "3.9"

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    container_name: kafka-zookeeper
    restart: unless-stopped
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    volumes:
      - zk-data:/var/lib/zookeeper/data
      - zk-log:/var/lib/zookeeper/log

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    container_name: linkedin-kafka
    restart: unless-stopped
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      # PLAINTEXT_INTERNAL = inter-container comms
      # PLAINTEXT_EXTERNAL = other EC2 instances connecting on public IP
      KAFKA_LISTENERS: PLAINTEXT_INTERNAL://0.0.0.0:29092,PLAINTEXT_EXTERNAL://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT_INTERNAL://kafka:29092,PLAINTEXT_EXTERNAL://${PUBLIC_ADDR}:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT_INTERNAL:PLAINTEXT,PLAINTEXT_EXTERNAL:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT_INTERNAL
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      KAFKA_LOG_RETENTION_HOURS: 168
    volumes:
      - kafka-data:/var/lib/kafka/data

volumes:
  zk-data:
  zk-log:
  kafka-data:
COMPOSE

echo "[START] Launching Kafka..."
docker compose up -d

echo "[WAIT] Waiting for Kafka to be ready..."
until docker exec linkedin-kafka kafka-topics --bootstrap-server localhost:9092 --list &>/dev/null; do
  sleep 3
done

echo "[TOPICS] Creating required topics..."
for topic in \
  "job.events" \
  "application.events" \
  "member.events" \
  "analytics.events" \
  "benchmark.completed" \
  "notification.events"; do
  docker exec linkedin-kafka kafka-topics \
    --bootstrap-server localhost:9092 \
    --create --if-not-exists \
    --topic "$topic" \
    --partitions 3 \
    --replication-factor 1
  echo "  Created: $topic"
done

echo ""
echo "======================================================================"
echo " Kafka is running on $PUBLIC_ADDR:9092"
echo ""
echo " Other services should set:"
echo "   KAFKA_BOOTSTRAP_SERVERS=$PUBLIC_ADDR:9092"
echo ""
echo " MANUAL STEPS REQUIRED:"
echo "   1. Open EC2 Security Group: inbound TCP 9092 from 0.0.0.0/0"
echo "   2. Verify from another machine:"
echo "      nc -zv $PUBLIC_ADDR 9092"
echo "======================================================================"
