#!/usr/bin/env bash
set -euo pipefail

topics=(
  user.created
  member.created
  member.updated
  member.deleted
  member.update.requested
  job.create.requested
  job.update.requested
  job.close.requested
  job.save.requested
  job.unsave.requested
  job.created
  job.viewed
  job.updated
  job.closed
  job.saved
  application.started
  application.submitted
  application.status.updated
  application.note.added
  thread.opened
  message.sent
  connection.requested
  connection.accepted
  connection.rejected
  connection.withdrawn
  analytics.normalized
  benchmark.completed
  ai.requests
  ai.results
  ai.rejected
  member.media.uploaded
  profile.viewed
  dlq.application.submitted
  dlq.application.status.updated
  dlq.message.sent
  dlq.connection.requested
  dlq.connection.accepted
  dlq.job.created
  dlq.ai.requests
)

for topic in "${topics[@]}"; do
  echo "Ensuring topic: $topic"
  docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh     --bootstrap-server kafka:9092     --create --if-not-exists --topic "$topic" >/dev/null
  done

echo "Kafka topics ready."
