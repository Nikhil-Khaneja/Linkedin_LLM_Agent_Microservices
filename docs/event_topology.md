# Kafka Event Topology

This build uses Kafka as the default cross-service transport for all business-domain events other than login/auth token exchange.

## Transactional owners (MySQL)
- `auth_service`: users, refresh tokens
- `member_profile_service`: members
- `recruiter_company_service`: recruiters, companies
- `jobs_service`: jobs, saved_jobs
- `applications_service`: applications, application_notes

## Read models / append-heavy documents (MongoDB)
- messaging threads and messages
- connection requests / graph documents
- notifications
- analytics raw events and rollups
- AI tasks / outputs
- member inbox projections and event-consumption ledgers

## Topic contracts
- `member.created`, `member.updated`, `member.deleted`
- `job.created`, `job.updated`, `job.closed`, `job.viewed`, `job.saved`
- `application.started`, `application.submitted`, `application.status.updated`, `application.note.added`
- `thread.opened`, `message.sent`
- `connection.requested`, `connection.accepted`, `connection.rejected`, `connection.withdrawn`
- `profile.viewed`
- `member.media.uploaded`
- `ai.requests`, `ai.results`, `ai.rejected`
- `analytics.normalized`, `benchmark.completed`

## Producer / consumer matrix

### jobs_service
Produces:
- `job.created`
- `job.updated`
- `job.closed`
- `job.viewed`
- `job.saved`

Consumes:
- none (source of truth for job write model)

### applications_service
Produces:
- `application.started`
- `application.submitted`
- `application.status.updated`
- `application.note.added`

Consumes:
- none (source of truth for application write model)

### messaging_connections_service
Produces:
- `thread.opened`
- `message.sent`
- `connection.requested`
- `connection.accepted`
- `connection.rejected`
- `connection.withdrawn`

### member_profile_service
Consumes:
- `connection.requested`
- `connection.accepted`
- `connection.rejected`
- `connection.withdrawn`
- `message.sent`
- `member.media.uploaded`

Materialized side effects:
- notification documents
- member inbox projection
- member connection event ledger
- member `connections_count` updates on accepted connections

### analytics_service
Consumes:
- `job.viewed`
- `job.saved`
- `application.started`
- `application.submitted`
- `application.status.updated`
- `application.note.added`
- `message.sent`
- `connection.requested`
- `connection.accepted`
- `connection.rejected`
- `profile.viewed`
- `ai.results`
- `benchmark.completed`

Produces:
- `analytics.normalized`

### ai_orchestrator_service
Consumes:
- `ai.requests`
- `ai.results`

Produces:
- `ai.requests`
- `ai.results`
- `ai.rejected`

## Design intent
- MySQL owns transactional state.
- MongoDB owns document/read-model workloads and projections.
- Kafka is the middleware for cross-service propagation, analytics, notifications, and async AI/media workflows.
- Every cross-service consumer is idempotent via event idempotency keys plus a consumption ledger where needed.
