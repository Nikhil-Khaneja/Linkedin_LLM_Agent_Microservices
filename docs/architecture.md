# Architecture Summary

## Why MySQL vs MongoDB

### MySQL
Used for strongly consistent transactional entities and business invariants:
- members
- recruiters
- companies
- jobs
- saved jobs
- applications
- application notes
- auth tables
- outbox events / idempotency keys

Why:
- foreign-key-like integrity requirements
- duplicate prevention
- state-transition validation (`job` open/closed, one application per member/job, one save per member/job)
- AWS-friendly operational model with RDS/Aurora MySQL

### MongoDB
Used for flexible document and projection workloads:
- messaging threads / messages
- connection graph documents / requests
- notifications
- analytics event store and rollups
- AI task documents and outputs
- member-side inbox and event projections

Why:
- append-heavy event capture
- denormalized read models
- fast iteration for AI/output payloads and notification schemas
- operational fit for projection stores

## Service boundaries
- `auth_service`: authentication only
- `member_profile_service`: member profile write model + member-facing projections from Kafka
- `recruiter_company_service`: recruiter/company write model
- `jobs_service`: job posting write model + save-job workflow
- `applications_service`: application write model + status/note workflows
- `messaging_connections_service`: conversations and connection graph write model
- `analytics_service`: event consumer + aggregate rollups + benchmark storage
- `ai_orchestrator_service`: asynchronous recruiter copilot workflows

## Cross-service integration pattern
1. owner service writes MySQL transaction
2. owner service writes outbox row in same DB transaction when applicable
3. background dispatcher publishes Kafka event
4. downstream services consume and build Mongo projections / derived MySQL counters

## Assignment-specific flows covered
- save jobs: `jobs_service` + `job.saved` analytics rollup
- apply to closed job: enforced in `applications_service`
- funnel analytics: `job.viewed`, `job.saved`, `application.started`, `application.submitted`
- recruiter/member messaging + connections: Kafka pub-sub plus member projections
- media upload / resume parsing: async event flow via `member.media.uploaded`
- AI shortlist / outreach: async workflow plus human approval gate

## Scale support
- `scripts/seed_perf_data.py` seeds up to 10,000+ members, recruiters/companies, and jobs directly into MySQL in chunks
- `scripts/run_performance_benchmarks.py` records live benchmark runs into analytics so the frontend renders measured rather than hardcoded values
