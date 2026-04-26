// ============================================================
// LinkedIn Distributed System - MongoDB Schema Init
// ============================================================
// Collections:
//   messages         – message bodies per thread (Owner 6)
//   agent_tasks      – AI task traces & results (Owner 8)
//   analytics_events – raw event log (Owner 7)
//   member_meta      – unstructured profile sections (Owner 2)
//   resume_parsed    – AI-parsed resume data (Owner 8)
// ============================================================

db = db.getSiblingDB('linkedin_nosql');

// ─────────────────────────────────────────────
// messages
// ─────────────────────────────────────────────
db.createCollection('messages', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['thread_id', 'sender_id', 'content', 'sent_at'],
      properties: {
        thread_id:   { bsonType: 'string' },
        sender_id:   { bsonType: 'string' },
        content:     { bsonType: 'string', maxLength: 5000 },
        sent_at:     { bsonType: 'date' },
        trace_id:    { bsonType: 'string' },
        idempotency_key: { bsonType: 'string' },
        is_deleted:  { bsonType: 'bool' }
      }
    }
  }
});
db.messages.createIndex({ thread_id: 1, sent_at: -1 });
db.messages.createIndex({ sender_id: 1 });
db.messages.createIndex({ idempotency_key: 1 }, { unique: true, sparse: true });

// ─────────────────────────────────────────────
// agent_tasks
// ─────────────────────────────────────────────
db.createCollection('agent_tasks', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['task_id', 'recruiter_id', 'job_id', 'task_type', 'status', 'created_at'],
      properties: {
        task_id:        { bsonType: 'string' },
        recruiter_id:   { bsonType: 'string' },
        job_id:         { bsonType: 'string' },
        task_type:      { enum: ['shortlist', 'outreach_draft', 'resume_parse', 'match_score', 'full_pipeline', 'shortlist_and_outreach'] },
        status:         { enum: ['queued', 'running', 'waiting_approval', 'approved', 'rejected', 'completed', 'failed'] },
        trace_id:       { bsonType: 'string' },
        steps:          { bsonType: 'array' },
        current_step:   { bsonType: 'string' },
        input_payload:  { bsonType: 'object' },
        output:         { bsonType: ['object', 'null'] },
        approval_note:  { bsonType: 'string' },
        approved_by:    { bsonType: 'string' },
        error_message:  { bsonType: 'string' },
        created_at:     { bsonType: 'date' },
        updated_at:     { bsonType: 'date' }
      }
    }
  }
});
db.agent_tasks.createIndex({ task_id: 1 }, { unique: true });
db.agent_tasks.createIndex({ recruiter_id: 1, created_at: -1 });
db.agent_tasks.createIndex({ status: 1 });
db.agent_tasks.createIndex({ trace_id: 1 });

// ─────────────────────────────────────────────
// analytics_events  (raw event log)
// ─────────────────────────────────────────────
db.createCollection('analytics_events');
db.analytics_events.createIndex({ event_type: 1, timestamp: -1 });
db.analytics_events.createIndex({ actor_id: 1 });
db.analytics_events.createIndex({ 'entity.entity_id': 1 });
db.analytics_events.createIndex({ trace_id: 1 });
db.analytics_events.createIndex({ timestamp: -1 }, { expireAfterSeconds: 7776000 }); // 90 days TTL

// ─────────────────────────────────────────────
// member_meta  (unstructured / flexible fields)
// ─────────────────────────────────────────────
db.createCollection('member_meta');
db.member_meta.createIndex({ member_id: 1 }, { unique: true });

// ─────────────────────────────────────────────
// resume_parsed  (AI-extracted resume fields)
// ─────────────────────────────────────────────
db.createCollection('resume_parsed');
db.resume_parsed.createIndex({ member_id: 1 });
db.resume_parsed.createIndex({ 'skills': 1 });

print('MongoDB collections and indexes initialized.');
