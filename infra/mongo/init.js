const dbName = 'linkedin_sim_docs';
const docDb = db.getSiblingDB(dbName);

function ensureCollection(name) {
  const existing = docDb.getCollectionNames();
  if (!existing.includes(name)) {
    docDb.createCollection(name);
  }
}

['threads', 'messages', 'connection_requests', 'connections', 'events', 'events_rollup', 'benchmarks', 'ai_tasks', 'ai_task_steps', 'outbox_events'].forEach(ensureCollection);

docDb.threads.createIndex({ participant_key: 1 }, { unique: true, background: true });
docDb.threads.createIndex({ latest_message_at: -1 }, { background: true });
docDb.messages.createIndex({ thread_id: 1, sent_at: -1 }, { background: true });
docDb.messages.createIndex({ thread_id: 1, client_message_id: 1 }, { unique: true, background: true, sparse: true });
docDb.connection_requests.createIndex({ requester_id: 1, receiver_id: 1, status: 1 }, { background: true });
docDb.connections.createIndex({ pair_key: 1 }, { unique: true, background: true });
docDb.connections.createIndex({ user_a: 1 }, { background: true });
docDb.connections.createIndex({ user_b: 1 }, { background: true });
docDb.events.createIndex({ idempotency_key: 1 }, { unique: true, background: true, sparse: true });
docDb.events.createIndex({ event_type: 1, timestamp: -1 }, { background: true });
docDb.events_rollup.createIndex({ rollup_id: 1 }, { unique: true, background: true });
docDb.events_rollup.createIndex({ kind: 1, job_id: 1 }, { background: true });
docDb.ai_tasks.createIndex({ task_id: 1 }, { unique: true, background: true });
docDb.ai_task_steps.createIndex({ task_id: 1, step_order: 1 }, { background: true });
docDb.outbox_events.createIndex({ idempotency_key: 1 }, { unique: true, background: true, sparse: true });
docDb.outbox_events.createIndex({ status: 1, created_at: 1 }, { background: true });
print(`MongoDB init complete for ${dbName}`);
