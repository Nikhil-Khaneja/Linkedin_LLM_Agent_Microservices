# LinkedIn Simulation — Project Audit & Implementation Plan

---

## PART 1 — AUDIT: What Is Implemented vs. Pending

### 1.1 Overall Architecture Status

The project is a **well-structured multi-service monorepo** with a clear ownership model. The skeleton, shared infrastructure, and most service logic are in place. The gaps are not structural — they are specific missing behaviors and missing integration wiring.

---

### 1.2 What Is Implemented

#### Infrastructure & Shared Layer
| Component | Status | Notes |
|---|---|---|
| Docker Compose (all services + Kafka KRaft + MySQL + MongoDB + Redis) | ✅ Done | Full local stack |
| Shared Kafka bus (`kafka_bus.py`) | ✅ Done | Real Kafka via aiokafka; memory mode for tests only |
| Shared Redis cache (`cache.py`) | ✅ Done | get_json/set_json/delete_pattern |
| Shared `build_event()` with full envelope | ✅ Done | Matches required JSON envelope: event_type, trace_id, timestamp, actor_id, entity, payload, idempotency_key |
| RS256 JWT authentication + JWKS | ✅ Done | Owner 1 issues; other services validate offline |
| Transactional outbox (MySQL) | ✅ Done | Jobs + Applications: write DB + outbox in same transaction |
| Document outbox (MongoDB) | ✅ Done | Messaging + AI service |
| Idempotency key enforcement | ✅ Done | submit, updateStatus, send_message, create_task |
| Prometheus + Grafana observability | ✅ Done | /ops/healthz, /ops/cache-stats, /ops/metrics |
| Bootstrap scripts | ✅ Done | bootstrap_local.sh, apply_mysql_schema.sh, create_kafka_topics.sh |
| AWS multi-account deploy config | ✅ Done | validate_multi_account.py, deploy/aws_accounts/ |

#### Tier 3 — Database
| Component | Status | Notes |
|---|---|---|
| MySQL: users, refresh_tokens, idempotency_keys | ✅ Done | Auth tables with indexes |
| MySQL: members | ✅ Done | Includes resume_text, skills_json, experience_json, education_json, profile_views, connections_count |
| MySQL: recruiters, companies | ✅ Done | Company industry, size, access_level |
| MySQL: jobs | ✅ Done | title, description_text, seniority_level, employment_type, location_text, work_mode, status |
| MySQL: applications | ✅ Done | UNIQUE(job_id, member_id), status enum, resume_ref, cover_letter |
| MySQL: saved_jobs | ✅ Done | UNIQUE(member_id, job_id) |
| MySQL: Indexes | ✅ Done | email, location, recruiter, company, status, created_at on all key tables |
| MongoDB: threads, messages | ✅ Done | Document store |
| MongoDB: connections, connection_requests | ✅ Done | Graph documents |
| MongoDB: notifications | ✅ Done | Member inbox projections |
| MongoDB: analytics events + rollups | ✅ Done | events_rollup materialized on ingest |
| MongoDB: AI task documents | ✅ Done | Task traces, step results, status transitions |

**Missing from schema:**
- `salary_range` not a first-class column in `jobs` — stored only in `payload_json` (risk: not queryable for filtering)
- `views_count` and `applicants_count` not tracked as explicit columns in `jobs` — derived from analytics (acceptable, but no denormalized counter for quick reads)
- `posted_datetime` not an explicit column in `jobs` — uses `created_at` (functionally equivalent)

#### Tier 2 — Services & APIs
| Service | Endpoints Implemented | Status |
|---|---|---|
| auth_service (port 8001) | /auth/register, /auth/login, /auth/refresh | ✅ Done |
| member_profile_service (port 8002) | /members/create, get, update, delete, search | ✅ Done |
| recruiter_company_service (port 8003) | /recruiters/create, get, update, delete, search | ✅ Done |
| jobs_service (port 8004) | /jobs/create, get, update, search, close, byRecruiter, save, unsave, savedByMember | ✅ Done |
| applications_service (port 8005) | /applications/submit, start, get, byJob, byMember, updateStatus, addNote | ✅ Done |
| messaging_connections_service (port 8006) | /threads/open, get, byUser; /messages/list, send; /connections/request, accept, reject, list, mutual, sent, withdraw, pending | ✅ Done |
| analytics_service (port 8007) | /events/ingest, /analytics/jobs/top, funnel, geo, member/dashboard, /benchmarks/report, list | ✅ Done |
| ai_orchestrator_service (port 8008) | /ai/tasks/create, list, get, approve, reject, sendOutreach; WS /ws/ai/tasks/{id} | ✅ Done |

#### Kafka Topics & Event Topology
| Domain | Topics | Status |
|---|---|---|
| Member | member.created, updated, deleted, update.requested, media.uploaded, profile.viewed | ✅ Defined |
| Job | job.create.requested, update.requested, close.requested, save.requested, created, updated, closed, viewed, saved | ✅ Defined |
| Application | application.started, submitted, status.updated, note.added | ✅ Defined |
| Messaging | thread.opened, message.sent | ✅ Defined |
| Connections | connection.requested, accepted, rejected, withdrawn | ✅ Defined |
| AI | ai.requests, ai.results, ai.rejected | ✅ Defined |
| Analytics | analytics.normalized, benchmark.completed | ✅ Defined |

**Kafka consumption is live in:** analytics_service, member_profile_service (projections), ai_orchestrator_service
**Kafka production via outbox in:** jobs_service, applications_service, messaging_connections_service, auth_service

#### Agentic AI Layer
| Component | Status | Notes |
|---|---|---|
| Resume Parser Skill | ✅ Done | Extracts skills (COMMON_SKILLS dict + profile data), years of experience (regex + experience entries), education, certifications |
| Job–Candidate Matching Skill | ✅ Done | Embedding similarity (HashingEmbeddingService) + skills overlap + experience score + location bonus + education score |
| Hiring Assistant Agent (Supervisor) | ✅ Done | Orchestrates: Resume Parser → Matching → Outreach draft via OpenRouter LLM |
| Human-in-the-loop (approve/reject/edit outreach) | ✅ Done | /ai/tasks/{id}/approve, reject, sendOutreach endpoints |
| WebSocket streaming to UI | ✅ Done | /ws/ai/tasks/{task_id} |
| Kafka orchestration (ai.requests → consumer → ai.results) | ✅ Done | AIOrchestratorService consumes ai.requests, runs workflow, publishes to ai.results |
| OpenRouter LLM client | ✅ Done | For outreach draft generation |
| AI task persistence (traces, step results) | ✅ Done | MongoDB AI task documents |
| Career Coach Agent | ❌ Missing | Optional per spec, but encouraged — not present |

#### Analytics Dashboards
| Graph Required | Status |
|---|---|
| Recruiter: Top 10 job postings by applications/month | ✅ API done (/analytics/jobs/top) — frontend in RecruiterDashboard.jsx |
| Recruiter: City-wise applications per month for a job | ✅ API done (/analytics/geo) |
| Recruiter: Top 5 low traction jobs | ⚠️ Partial — /analytics/jobs/top exists but no explicit "fewest applications" filter exposed in UI |
| Recruiter: Clicks per job posting (from logs) | ✅ job.viewed events consumed by analytics_service |
| Recruiter: Saved jobs per day/week (from logs) | ✅ job.saved events consumed by analytics_service |
| Member: Profile views last 30 days | ✅ API done (/analytics/member/dashboard) |
| Member: Application status breakdown | ✅ API done |

#### Frontend (React)
| Page | Status |
|---|---|
| Login / Register | ✅ Done |
| Jobs search + filter + save + apply | ✅ Done |
| Job Detail | ✅ Done |
| Member Profile (create/edit) | ✅ Done |
| Applications (member view) | ✅ Done |
| Messaging (threads + send) | ✅ Done |
| Connections | ✅ Done |
| Notifications | ✅ Done (page exists) |
| Member Dashboard (analytics) | ✅ Done |
| Recruiter Dashboard | ✅ Done |
| AI Dashboard (task creation, status, approve/reject) | ✅ Done |
| Analytics Page | ✅ Done |

#### Testing & Performance
| Component | Status |
|---|---|
| API smoke tests (pytest) | ✅ 5 passed |
| JMeter Scenario A .jmx (job search + detail) | ✅ File exists |
| JMeter Scenario B .jmx (apply submit) | ✅ File exists |
| Seed script for 10,000+ records | ✅ seed_perf_data.py exists |
| Actual benchmark run results | ❌ Not yet run — no charts produced |
| B / B+S / B+S+K / B+S+K+Other bar charts | ❌ Not yet done |

#### Exception Handling
| Failure Case | Status |
|---|---|
| Duplicate email on register | ✅ UNIQUE constraint on users.email |
| Duplicate application to same job | ✅ UNIQUE KEY (job_id, member_id) in applications |
| Apply to closed job | ✅ Status check in applications_service |
| Message send retry | ⚠️ Idempotency key on /messages/send, but no explicit client-side retry UI |
| Kafka consumer failure + idempotency | ✅ consumption ledger + idempotency_key checks |
| Multi-step partial failure | ✅ Transactional outbox (MySQL) and document outbox (MongoDB) ensure consistency |

---

### 1.3 What Is Pending / Gaps

#### GAP 1 — Kafka-First Flow for Tier 1 Client Features (CRITICAL — Addon #2)

**Current state:** The write path is synchronous: `UI → REST → service → DB write → outbox → Kafka`. Kafka is used for cross-service propagation downstream. This is the "outbox pattern" — correct for reliability, but it does NOT implement the required:

> "UI produces → Kafka → backend consumes → DB update → UI notification"

The topics `job.create.requested`, `job.update.requested`, `member.update.requested`, `job.save.requested` are defined in create_kafka_topics.sh but there are NO consumers for these request topics — they appear to be placeholders.

**What is required:** At minimum one complete Kafka-first flow must exist:
- UI calls a "producer endpoint" that ONLY publishes to Kafka and returns `accepted`
- A background consumer processes the event, writes to DB, then triggers a UI notification
- The recommended flow for this is: **Job Apply** or **Connection Request**

**Suggested change:** Wire `application.submit` as a true async Kafka-first flow:
1. `/applications/submit` → publish `application.submitted` to Kafka → return `{status: "accepted", trace_id}`
2. Worker consumer reads `application.submitted` → writes to DB
3. Worker publishes `application.status.updated` notification
4. UI polls or WebSocket receives the DB confirmation

---

#### GAP 2 — Missing salary_range as Queryable Column in jobs Table

**Current state:** `salary_range` lives in `payload_json` only.

**What is required:** The spec lists `salary_range (optional)` as a job entity field. For search/filter to work on salary, it must be a first-class column.

**Suggested change:** Add `salary_min INT NULL, salary_max INT NULL, salary_currency VARCHAR(8) NULL DEFAULT 'USD'` to the jobs table.

---

#### GAP 3 — AI Evaluation Metrics Not Reported (Section 7.3)

**Current state:** Match scores are computed and stored per task, but there is no:
- Dashboard or endpoint that reports aggregate matching quality (top-k skills overlap distribution)
- Endpoint that reports human-in-the-loop approval rate (% approved as-is vs edited vs rejected)

**What is required:** At minimum 2 evaluation metrics must be reported.

**Suggested change:**
- Add `ai_approval_action` field to AI task documents: `approved_as_is | edited | rejected`
- Add endpoint `/ai/analytics/approval-rate` that returns approval/edit/reject distribution
- Add endpoint `/ai/analytics/match-quality` that reports average match score and skill overlap % across shortlisted candidates

---

#### GAP 4 — Datasets Not Integrated

**Current state:** `seed_perf_data.py` generates synthetic data. There is no pipeline to load Kaggle job or resume datasets.

**What is required:** At least one real jobs dataset and one real resume dataset must be used.

**Which categories are needed:**
- **Jobs dataset**: job title, description, skills_required, location, employment_type, seniority_level, company_name, company_industry
- **Resumes dataset**: resume_text or structured fields: skills, education, years_experience, current_title

**Suggested datasets (per spec):**
- Jobs: `kaggle datasets download rajatraj0502/linkedin-job-2023`
- Resumes: `kaggle datasets download snehaanbhawal/resume-dataset`

**Action needed:** Write `scripts/load_kaggle_datasets.py` that reads CSV/JSON from the dataset files and inserts into MySQL jobs and members tables.

---

#### GAP 5 — JMeter Benchmark Runs Not Executed / No Performance Charts

**Current state:** `.jmx` files exist for Scenario A and B. No results have been captured.

**What is required:** 4 bar charts comparing throughput/latency for: B, B+S, B+S+K, B+S+K+Other across 100 concurrent users.

**Action needed:**
- Run JMeter against local stack (Scenario A: job search, Scenario B: apply submit)
- Run 4 configurations: base only, base+Redis, base+Redis+Kafka, base+Redis+Kafka+replicas
- Record latency p50/p95 and throughput (req/sec)
- Store results via `POST /benchmarks/report` so the frontend AnalyticsPage can render them

---

#### GAP 6 — Top 5 Low Traction Jobs Not Surfaced in Recruiter Dashboard UI

**Current state:** The analytics API returns top jobs sorted by metric, but the UI does not explicitly render "Top 5 Fewest Applications" (low traction) as a separate chart.

**Action needed:** Add a second call in `RecruiterDashboard.jsx` with `sort: "asc"` and `limit: 5` to render a "Low Traction Jobs" bar chart.

---

#### GAP 7 — Career Coach Agent (Encouraged Optional)

**Current state:** Not implemented.

**What is needed:** A FastAPI endpoint `/ai/coach/suggest` that accepts `{member_id, target_job_id}`, calls Resume Parser + Matching, and uses the LLM to generate headline/resume suggestions with rationale.

**Effort:** Low — can reuse the existing `ai_resume_intelligence.py` + `OpenRouterClient`. Add one new workflow in `ai_service.py`.

---

#### GAP 8 — Notifications WebSocket / Real-time Push Not Wired to Frontend

**Current state:** Notification documents are created in MongoDB when connections/messages arrive. The Notifications page exists in the frontend. But there is no WebSocket or polling endpoint in the frontend to receive real-time Kafka-driven notifications.

**Action needed:** The member_profile_service already materializes notifications. Add a `/notifications/poll` REST endpoint (or WS), and wire it in `NotificationsPage.jsx`.

---

### 1.4 Suggested Structural Changes

| Change | Reason |
|---|---|
| Add `salary_min`, `salary_max` columns to `jobs` table | Enables salary-range filtering in job search |
| Wire `application.submit` as true async Kafka-first flow | Satisfies Addon #2 and Section 6.1 requirement |
| Add AI evaluation metrics endpoints | Satisfies Section 7.3 (required) |
| Write Kaggle dataset loader script | Satisfies Section 9 (required) |
| Run JMeter + produce 4 benchmark charts | Satisfies Section 11 + grading |
| Add notification polling/WS in frontend | Completes the end-to-end async notification loop |
| Add Top-5-Low-Traction chart to Recruiter Dashboard | Satisfies Section 8.1 requirement |

---

---

## PART 2 — SYSTEM DESIGN, AI ARCHITECTURE, DB SCHEMAS & 4-PERSON IMPLEMENTATION PLAN

---

### 2.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TIER 1 — CLIENT                                │
│                          React SPA (Vite, port 5173)                        │
│                                                                             │
│  Pages: Login | Register | Jobs | Job Detail | Apply | Profile             │
│         Messaging | Connections | Notifications | AI Dashboard             │
│         Member Analytics | Recruiter Dashboard                             │
│                                                                             │
│  Client produces Kafka events via REST "producer" endpoints                 │
│  Client receives real-time updates via WebSocket (AI tasks, notifications)  │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │ HTTPS / Bearer JWT (RS256)
┌────────────────────▼────────────────────────────────────────────────────────┐
│                           TIER 2 — SERVICES + KAFKA                         │
│                                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Owner 1  │  │  Owner 2  │  │  Owner 3  │  │  Owner 4  │  │  Owner 5  │  │
│  │  auth     │  │  member   │  │ recruiter │  │   jobs    │  │  apply    │  │
│  │  :8001    │  │  :8002    │  │  :8003    │  │   :8004   │  │  :8005    │  │
│  └────┬──────┘  └────┬──────┘  └────┬──────┘  └────┬──────┘  └────┬──────┘  │
│       │              │              │              │              │          │
│  ┌──────────┐  ┌──────────────────────────────────────────────────────┐    │
│  │  Owner 6  │  │              KAFKA (KRaft mode)                      │    │
│  │ messaging │  │                                                      │    │
│  │  :8006    │  │  Topics (producers → consumers):                     │    │
│  └────┬──────┘  │                                                      │    │
│       │         │  member.*  ──────────────►  member_profile_service   │    │
│  ┌──────────┐  │  job.*     ──────────────►  analytics_service        │    │
│  │  Owner 7  │  │  application.* ──────────►  analytics_service        │    │
│  │analytics  │  │  message.sent ───────────►  member_profile_service   │    │
│  │  :8007    │  │  connection.* ───────────►  member_profile_service   │    │
│  └────┬──────┘  │  ai.requests  ───────────►  ai_orchestrator_service  │    │
│       │         │  ai.results   ───────────►  analytics_service        │    │
│  ┌──────────┐  └──────────────────────────────────────────────────────┘    │
│  │  Owner 8  │                                                              │
│  │    AI     │         Redis (cache: job detail, search, unread counts,    │
│  │  :8008    │                  analytics rollups, AI task state)          │
│  └────┬──────┘                                                              │
│       │                                                                     │
└───────┼─────────────────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────────────────┐
│                           TIER 3 — DATABASES                                │
│                                                                             │
│   MySQL (RDS/Aurora in AWS)                  MongoDB Atlas / DocumentDB     │
│   ─────────────────────────                  ─────────────────────────      │
│   users, refresh_tokens                      threads, messages              │
│   idempotency_keys                           connection_requests             │
│   members                                    connection_graph_docs           │
│   recruiters, companies                      notifications                   │
│   jobs, saved_jobs                           analytics_events                │
│   applications, application_notes            events_rollup                   │
│   outbox_events                              ai_tasks, ai_outputs            │
│                                              member_projections              │
└─────────────────────────────────────────────────────────────────────────────┘


AWS Deployment Topology (per owner account):
─────────────────────────────────────────────
  Owner 1 AWS account:  auth_service + RDS MySQL (shared)
  Owner 2 AWS account:  member_profile_service + MSK Kafka shared topic
  Owner 3 AWS account:  recruiter_company_service
  Owner 4 AWS account:  jobs_service + Redis ElastiCache
  (All owners share: MSK Kafka cluster, RDS MySQL, DocumentDB/MongoDB Atlas)
```

---

### 2.2 Kafka-First Async Flow Diagram (Required End-to-End Workflow)

```
Application Submit — Full Async Kafka-First Flow
─────────────────────────────────────────────────

  Browser (Member)
       │
       │  POST /applications/submit  {job_id, member_id, resume_ref}
       ▼
  applications_service (port 8005)
       │
       ├─── Validate: job exists + is open + no duplicate (MySQL check)
       │
       ├─── Write to DB + outbox in SAME MySQL transaction:
       │       INSERT INTO applications (...)
       │       INSERT INTO outbox_events (topic='application.submitted', ...)
       │
       ├─── Return HTTP 202 Accepted: {trace_id, application_id}
       │
  Background outbox dispatcher (same service):
       │
       ├─── Reads unprocessed outbox rows
       ├─── Publishes to Kafka topic: application.submitted
       │    Envelope: {event_type, trace_id, actor_id, entity, payload, idempotency_key}
       │
  Kafka broker:
       │
       ├─► analytics_service consumer group:
       │       Reads application.submitted
       │       Increments events_rollup (applicants_count for job, funnel step)
       │       Idempotency check before write
       │
       ├─► member_profile_service consumer group:
       │       Reads application.submitted
       │       Creates notification document in MongoDB for member
       │       Updates member inbox projection
       │
  member_profile_service:
       │
       └─► WebSocket push / notification poll to Browser (Member)
               UI updates: "Your application was submitted!"
               Application status card changes to "submitted"
```

---

### 2.3 AI Architecture Diagram

```
Agentic AI — Hiring Assistant Workflow
───────────────────────────────────────

  Recruiter Browser
       │
       │  POST /ai/tasks/create  {job_id, recruiter_id}
       ▼
  ai_orchestrator_service (port 8008)
       │
       ├─── Creates AI task document in MongoDB (status: pending)
       ├─── Publishes to Kafka: ai.requests
       │    {event_type: "ai.requested", entity: {job_id}, payload: {task_id}}
       │
       ├─── Returns HTTP 202: {task_id, trace_id}
       │
  Browser opens WebSocket: /ws/ai/tasks/{task_id}
       │
       │
  Kafka consumer (same service, ai.requests topic):
       │
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │          Hiring Assistant Agent (Supervisor)                 │
  │                                                             │
  │  Step 1: Fetch job from jobs_service                        │
  │          Fetch applications for job from applications_service│
  │          Fetch member profiles from member_profile_service   │
  │                                                             │
  │  Step 2: Resume Parser Skill (per candidate)               │
  │  ┌──────────────────────────────────────────┐              │
  │  │  Input: resume_text + member profile      │              │
  │  │  Output: ParsedResume {                   │              │
  │  │    skills: [...],                         │              │
  │  │    years_experience: float,               │              │
  │  │    education: str,                        │              │
  │  │    certifications: [...]                  │              │
  │  │  }                                        │              │
  │  └──────────────────────────────────────────┘              │
  │                                                             │
  │  Step 3: Job–Candidate Matching Skill (per candidate)       │
  │  ┌──────────────────────────────────────────┐              │
  │  │  Input: job + ParsedResume + resume_text  │              │
  │  │  Scoring:                                 │              │
  │  │    base: 20 pts                           │              │
  │  │    skill overlap (35 pts max)             │              │
  │  │    embedding similarity (25 pts max)      │              │
  │  │    experience fit (20 pts max)            │              │
  │  │    location bonus (8 pts max)             │              │
  │  │    education (4 pts max)                  │              │
  │  │    keyword overlap (8 pts max)            │              │
  │  │  Output: match_score (0-100) + rationale  │              │
  │  └──────────────────────────────────────────┘              │
  │                                                             │
  │  Step 4: Sort + shortlist top-k candidates                  │
  │                                                             │
  │  Step 5: Outreach Draft (LLM via OpenRouter)               │
  │  ┌──────────────────────────────────────────┐              │
  │  │  Input: job + top candidate profiles      │              │
  │  │  LLM prompt → personalized outreach msg   │              │
  │  │  Output: draft_message per candidate      │              │
  │  └──────────────────────────────────────────┘              │
  │                                                             │
  │  Step 6: Publish to ai.results                              │
  │          Update task document (status: awaiting_approval)   │
  │          Push via WebSocket to recruiter browser            │
  └─────────────────────────────────────────────────────────────┘
       │
  Recruiter reviews in AI Dashboard:
       │
       ├── Approve as-is → POST /ai/tasks/{id}/approve
       │                   → POST /ai/tasks/{id}/sendOutreach
       │                   → messaging_service creates thread + sends message
       │
       ├── Edit message  → POST /ai/tasks/{id}/approve {edited_message: "..."}
       │
       └── Reject        → POST /ai/tasks/{id}/reject
                          → Logs action, updates approval_action = "rejected"

Kafka Topics for AI:
  ai.requests  →  Supervisor consumes, starts workflow
  ai.results   →  Supervisor publishes completed results; analytics_service consumes
  ai.rejected  →  Supervisor publishes on failure or rejection

Evaluation Metrics Tracked:
  - match_score per candidate (stored in task document)
  - approval_action: approved_as_is | edited | rejected
  - skill_overlap % per shortlisted candidate
  - Aggregate: /ai/analytics/approval-rate, /ai/analytics/match-quality
```

---

### 2.4 Database Schema (Complete)

#### MySQL Schema (Transactional — linkedin_sim DB)

```sql
-- AUTH
users (user_id PK, email UNIQUE, password_hash, subject_type,
       first_name, last_name, payload_json, skills_json,
       experience_json, education_json, created_at)

refresh_tokens (refresh_token_id PK, user_id FK, token_hash,
                is_revoked, created_at, expires_at)

idempotency_keys (idempotency_key PK, route_name, body_hash,
                  response_json, original_trace_id, created_at)

-- MEMBER
members (member_id PK, email, first_name, last_name, headline,
         about_text, location_text, profile_version, is_deleted,
         profile_views, connections_count, profile_photo_url,
         resume_url, resume_text MEDIUMTEXT, current_company,
         current_title, payload_json, skills_json,
         experience_json, education_json, created_at)

-- RECRUITER / COMPANY
recruiters (recruiter_id PK, company_id FK, email UNIQUE,
            name, phone, access_level, payload_json, created_at)

companies (company_id PK, company_name, company_industry,
           company_size, payload_json, created_at)

-- JOBS  [ADD: salary_min, salary_max]
jobs (job_id PK, company_id FK, recruiter_id FK, title,
      description_text, seniority_level, employment_type,
      location_text, work_mode, status DEFAULT 'open',
      salary_min INT NULL, salary_max INT NULL,          -- ADD
      salary_currency VARCHAR(8) DEFAULT 'USD',           -- ADD
      version, payload_json, skills_json, created_at)

saved_jobs (save_id PK, member_id, job_id,
            UNIQUE(member_id, job_id), created_at)

-- APPLICATIONS
applications (application_id PK, job_id FK, member_id FK,
              resume_ref, cover_letter, status DEFAULT 'submitted',
              application_datetime, payload_json,
              UNIQUE(job_id, member_id))

application_notes (note_id PK, application_id FK, recruiter_id,
                   note_text, created_at)

-- OUTBOX (Transactional)
outbox_events (outbox_id PK, topic, payload_json,
               is_dispatched BOOL DEFAULT FALSE,
               created_at, dispatched_at)

-- INDEXES (existing + additions)
idx_users_email, idx_members_email, idx_members_location
idx_recruiters_company, idx_jobs_recruiter, idx_jobs_company
idx_jobs_status, idx_jobs_location, idx_jobs_created_at
idx_applications_member, idx_applications_job, idx_applications_status
idx_jobs_salary (salary_min, salary_max)                  -- ADD
idx_outbox_dispatched (is_dispatched, created_at)         -- ADD
```

#### MongoDB Schema (Document — linkedin_db)

```
Collection: threads
{
  thread_id: str,
  participants: [str],         // user_ids
  created_at: ISO-8601,
  last_message_at: ISO-8601,
  unread_counts: {user_id: int}
}
Index: {participants: 1}, {last_message_at: -1}

Collection: messages
{
  message_id: str,
  thread_id: str,
  sender_id: str,
  receiver_id: str,
  message_text: str,
  timestamp: ISO-8601,
  idempotency_key: str
}
Index: {thread_id: 1, timestamp: 1}, {idempotency_key: 1}

Collection: connection_requests
{
  request_id: str,
  requester_id: str,
  receiver_id: str,
  status: 'pending'|'accepted'|'rejected'|'withdrawn',
  timestamp: ISO-8601
}
Index: {requester_id: 1}, {receiver_id: 1}, {status: 1}

Collection: connection_graph_docs
{
  user_id: str,
  connections: [str],          // accepted connection user_ids
  connections_count: int,
  updated_at: ISO-8601
}
Index: {user_id: 1}

Collection: notifications
{
  notification_id: str,
  user_id: str,
  event_type: str,
  payload: {},
  is_read: bool,
  created_at: ISO-8601
}
Index: {user_id: 1, is_read: 1, created_at: -1}

Collection: analytics_events
{
  event_id: str,
  event_type: str,
  trace_id: str,
  timestamp: ISO-8601,
  actor_id: str,
  entity: {entity_type, entity_id},
  payload: {},
  idempotency_key: str
}
Index: {event_type: 1, timestamp: -1}, {idempotency_key: 1}

Collection: events_rollup
{
  rollup_id: str,          // "{entity_type}:{entity_id}:{event_type}:{window}"
  entity_type: str,
  entity_id: str,
  event_type: str,
  window: str,             // "2025-05" or "2025-W18"
  count: int,
  city_breakdown: {city: count},
  last_updated: ISO-8601
}
Index: {entity_type: 1, event_type: 1, window: -1}

Collection: ai_tasks
{
  task_id: str,
  trace_id: str,
  recruiter_id: str,
  job_id: str,
  status: 'pending'|'processing'|'awaiting_approval'|'approved'|'rejected'|'sent'|'failed',
  shortlist: [CandidateArtifact],
  outreach_drafts: {candidate_id: str},
  approval_action: 'approved_as_is'|'edited'|'rejected'|null,
  edited_message: str|null,
  step_log: [{step, status, timestamp}],
  created_at: ISO-8601,
  completed_at: ISO-8601|null
}
Index: {recruiter_id: 1, status: 1}, {trace_id: 1}

Collection: outbox_documents  (for Owner 6, Owner 8)
{
  outbox_id: str,
  topic: str,
  payload: {},
  is_dispatched: bool,
  created_at: ISO-8601
}
Index: {is_dispatched: 1, created_at: 1}
```

---

### 2.5 Four-Person Implementation Plan

> Assumption: 4 people deploying to the same shared AWS account. All services share one MSK Kafka cluster, one RDS MySQL instance, one DocumentDB/MongoDB Atlas cluster, one ElastiCache Redis. Each person owns the work described below.

---

#### Person 1 — Kafka-First Flows + Exception Handling + Auth/Infra

**Owns:** auth_service, shared Kafka wiring, exception handling completeness, Docker/AWS infra

**Tasks:**
1. **Kafka-First Application Submit Flow**
   - Modify `applications_service`: `/applications/submit` → validate synchronously → write DB + outbox in transaction → return 202
   - The outbox dispatcher publishes `application.submitted`
   - `member_profile_service` consumer creates notification
   - Test the full loop: UI submit → Kafka → notification in browser
   - Add `/notifications/poll` endpoint in member_profile_service

2. **Kafka envelope compliance audit**
   - Verify all `publish_event` calls use `build_event()` (not ad-hoc dicts)
   - Add `service` field to all envelopes if not present
   - Ensure `trace_id` flows from UI request headers through Kafka payload through consumer

3. **Exception handling completeness**
   - Add duplicate email error (409) with clear message in auth_service `/auth/register`
   - Add message retry logic: client-side idempotency key on `/messages/send`
   - Add dead-letter handling in `consume_forever`: failed events → `dlq.{topic}` topic
   - Test all 6 failure cases from spec (duplicate email, duplicate application, closed job apply, message retry, Kafka consumer failure, partial multi-step failure)

4. **AWS infrastructure setup** (shared account)
   - Provision MSK Kafka cluster (3 brokers, KRaft mode or ZooKeeper)
   - Provision RDS MySQL 8.0 with `linkedin_sim` DB
   - Provision DocumentDB (or MongoDB Atlas free tier) with `linkedin_db`
   - Provision ElastiCache Redis (single node)
   - Run `scripts/apply_mysql_schema.sh` and `scripts/apply_mongo_init.sh` against AWS endpoints
   - Update `.env` with AWS endpoints; test `validate_multi_account.py`

5. **Notification WebSocket in frontend**
   - Add polling or WebSocket in `NotificationsPage.jsx` to pull from `/notifications/poll`
   - Show badge count in Layout header when unread > 0

**Deliverables:**
- Working end-to-end async flow: submit application → Kafka → notification in UI
- All 6 failure cases tested and passing
- AWS infra running and accessible

---

#### Person 2 — AI Completion + Evaluation Metrics + Career Coach

**Owns:** ai_orchestrator_service, AI evaluation metrics, Career Coach Agent

**Tasks:**
1. **AI Evaluation Metrics (Section 7.3 — Required)**
   - Add `approval_action` field to `ai_tasks` documents: `approved_as_is | edited | rejected`
   - Update `approve_task` to record `approved_as_is` if message not edited, `edited` if message changed
   - Update `reject_task` to record `rejected`
   - Add endpoint `GET /ai/analytics/approval-rate`:
     ```json
     {
       "total_tasks": 42,
       "approved_as_is": 18,
       "edited": 15,
       "rejected": 9,
       "approval_rate_pct": 42.8,
       "edit_rate_pct": 35.7
     }
     ```
   - Add endpoint `GET /ai/analytics/match-quality`:
     ```json
     {
       "avg_match_score": 67.3,
       "avg_skill_overlap_pct": 54.1,
       "top_k": 5,
       "sample_size": 200
     }
     ```

2. **Career Coach Agent (Encouraged Optional)**
   - Add endpoint `POST /ai/coach/suggest {member_id, target_job_id}`
   - Workflow: fetch member profile → fetch job → run Resume Parser + Matching → LLM prompt for headline/skills suggestions
   - Return: `{suggested_headline, skills_to_add, resume_tips, match_score_if_improved}`
   - Wire to a new `CareerCoachPage.jsx` in frontend

3. **AI Dashboard improvements**
   - Surface evaluation metrics on `AIDashboard.jsx`: approval rate pie chart, avg match score
   - Add Career Coach suggestion panel on `ProfilePage.jsx` (optional button: "Optimize for this job")

4. **AI Kafka multi-agent trace_id propagation**
   - Verify `trace_id` stays the same from the initial `/ai/tasks/create` REST call through `ai.requests` Kafka event through `ai.results` Kafka event
   - Log each step in `step_log` with `{step_name, trace_id, timestamp, status}`

5. **Testing AI workflows**
   - Write pytest test for the full AI workflow in sandbox (memory mode)
   - Assert task moves from `pending → processing → awaiting_approval`
   - Assert shortlist has at least 1 candidate with match_score > 0

**Deliverables:**
- Evaluation metrics endpoints live and returning data
- Career Coach Agent endpoint working
- AI task trace_id propagation verified
- AI tests passing

---

#### Person 3 — Analytics Dashboards + Datasets + Frontend Polish

**Owns:** analytics_service frontend, datasets, recruiter and member dashboard completeness

**Tasks:**
1. **Recruiter Dashboard — Low Traction Jobs Chart**
   - Add a second API call in `RecruiterDashboard.jsx` to `/analytics/jobs/top` with `{metric: "applications", sort: "asc", limit: 5}`
   - Render as "Jobs Needing Attention" bar chart

2. **Dataset Integration (Section 9 — Required)**
   - Download Kaggle datasets:
     - `kaggle datasets download rajatraj0502/linkedin-job-2023` → provides job title, description, company, location, type
     - `kaggle datasets download snehaanbhawal/resume-dataset` → provides resume text + category
   - Write `scripts/load_kaggle_datasets.py`:
     - Parse jobs CSV → normalize fields → insert into MySQL `jobs` table
     - Parse resumes CSV → normalize → insert into MySQL `members` table with `resume_text`
   - Supplement with synthetic fields (salary, skills_json) for fields not in dataset
   - Target: 10,000 jobs + 5,000 members seeded from real data

3. **Analytics completeness check + frontend charts**
   - Verify all 5 recruiter dashboard charts render correctly with real data:
     1. Top 10 jobs by applications per month (bar)
     2. City-wise applications for selected job (bar/map)
     3. Top 5 low traction jobs (bar)
     4. Clicks per job (line chart from job.viewed events)
     5. Saved jobs per day/week (line chart from job.saved events)
   - Verify 2 member dashboard charts: profile views 30 days (line), application status breakdown (pie)

4. **salary_range schema addition**
   - Add `salary_min INT NULL, salary_max INT NULL` to MySQL `jobs` table (new migration file `005_salary_range.sql`)
   - Update jobs_service job_repository.py to read/write salary fields
   - Update `/jobs/search` to support `{salary_min, salary_max}` filter
   - Update job search UI filter in `JobsPage.jsx`

5. **Frontend — views_count tracking**
   - In `JobDetailPage.jsx`, on mount call `/events/ingest` with `event_type: job.viewed`
   - In `ProfilePage.jsx`, on another user's profile view call `/events/ingest` with `event_type: profile.viewed`

**Deliverables:**
- Kaggle dataset loaded into DB with 10,000+ records
- All 7 dashboard charts (5 recruiter + 2 member) rendering with real data
- salary_range searchable in job search
- View tracking events firing from UI

---

#### Person 4 — JMeter Benchmarking + Redis Caching Validation + AWS Deployment

**Owns:** performance benchmarking, Redis caching impact, AWS ECS/EC2 deployment, performance write-up

**Tasks:**
1. **JMeter Benchmark Execution (Section 11 — Required)**
   - Load DB with 10,000+ records (use seed_perf_data.py)
   - Run 4 configurations with 100 concurrent threads:
     - **B** (Base): No Redis, No Kafka async, single service instance
     - **B+S** (Base + SQL Caching): Redis enabled (REDIS_ENABLED=true), same single instance
     - **B+S+K** (+ Kafka): Redis + Kafka outbox enabled, single instance
     - **B+S+K+Other**: Redis + Kafka + 2 service replicas in Docker Compose (scale: 2)
   - Record for both Scenario A (job search + detail) and Scenario B (apply submit):
     - Throughput (requests/sec)
     - Latency p50, p95, p99 (ms)
   - Store results via `POST /benchmarks/report` endpoint
   - The AnalyticsPage renders the 4 bar charts automatically from stored results

2. **Redis caching validation**
   - Verify Redis hit rate on `/ops/cache-stats` goes up after warm-up
   - Add cache stats to benchmark report: hit rate %, miss count
   - Document caching policy: what is cached, TTL, invalidation triggers

3. **AWS ECS Deployment**
   - Create ECR repositories for each service
   - Write `deploy/aws_accounts/ecs_task_definitions/` — one ECS task definition per service
   - Configure ALB + target groups per service
   - Set env vars: KAFKA_BOOTSTRAP_SERVERS (MSK), MYSQL_HOST (RDS), MONGO_URI (DocumentDB), REDIS_URL (ElastiCache)
   - Deploy frontend as S3 static + CloudFront (or Nginx EC2)
   - Document deployment steps in `docs/aws_deploy_step_by_step.md`

4. **Multi-replica test**
   - Run `docker compose up --scale jobs_service=2 --scale applications_service=2`
   - Verify Kafka consumer group balancing (two consumers split partitions)
   - Verify idempotency: duplicate submit with same idempotency_key returns same response, not duplicate DB write
   - Record throughput improvement vs single-replica baseline

5. **Performance write-up**
   - Write 1-page `docs/PERFORMANCE_ANALYSIS.md`:
     - Caching policy explanation (what/why/TTL/invalidation)
     - Messaging flow explanation (why Kafka improves throughput under load)
     - 4 bar charts with numbers
     - Observations and lessons

**Deliverables:**
- 4 benchmark configurations run, results in DB
- 4 bar charts visible in AnalyticsPage
- All services deployed to AWS ECS
- Performance write-up complete

---

### 2.6 Work Division Summary Table

| # | Area | Person | Priority | Effort |
|---|---|---|---|---|
| 1 | Kafka-first async application submit flow | Person 1 | CRITICAL | 2 days |
| 2 | Notification WebSocket/poll in frontend | Person 1 | HIGH | 1 day |
| 3 | Exception handling (all 6 cases) | Person 1 | HIGH | 1 day |
| 4 | AWS infrastructure provisioning | Person 1 | HIGH | 1 day |
| 5 | AI evaluation metrics endpoints | Person 2 | REQUIRED | 1 day |
| 6 | Career Coach Agent | Person 2 | ENCOURAGED | 2 days |
| 7 | AI dashboard metrics charts | Person 2 | MEDIUM | 0.5 day |
| 8 | Kaggle dataset loader script | Person 3 | REQUIRED | 1.5 days |
| 9 | Recruiter dashboard — low traction chart | Person 3 | REQUIRED | 0.5 day |
| 10 | salary_range column + search filter | Person 3 | MEDIUM | 1 day |
| 11 | View tracking events in frontend | Person 3 | MEDIUM | 0.5 day |
| 12 | All dashboard charts verified with real data | Person 3 | HIGH | 1 day |
| 13 | JMeter 4 benchmark runs + bar charts | Person 4 | REQUIRED | 2 days |
| 14 | AWS ECS deployment (all services) | Person 4 | REQUIRED | 2 days |
| 15 | Redis caching validation | Person 4 | HIGH | 0.5 day |
| 16 | Multi-replica Kafka consumer group test | Person 4 | HIGH | 0.5 day |
| 17 | Performance write-up | Person 4 | REQUIRED | 0.5 day |

---

### 2.7 Dataset Categories Needed

For Person 3 to load datasets, the following fields are needed from each dataset:

**From Jobs Dataset (linkedin-job-2023):**
- `title` → jobs.title
- `description` → jobs.description_text
- `company_name` → companies.company_name
- `location` → jobs.location_text
- `employment_type` → jobs.employment_type
- `seniority_level` → jobs.seniority_level
- `industry` → companies.company_industry

**From Resume Dataset:**
- `resume_str` or `resume_text` → members.resume_text
- `category` (job category) → members.current_title (inferred)

**Synthetic supplements to add per row:**
- `skills_json` — extract from resume text using `parse_resume()` from `ai_resume_intelligence.py`
- `salary_min`, `salary_max` — random range by seniority level
- `work_mode` — random: remote/hybrid/onsite (weighted 30/40/30)
- `member.headline` — "{current_title} at {current_company}"

---

### 2.8 Pre-Demo Checklist

Before the demo on 5/5, verify:

- [ ] `./scripts/bootstrap_local.sh` starts all services locally with no errors
- [ ] `pytest tests/api -q` passes all tests
- [ ] `scripts/load_kaggle_datasets.py` loaded 10,000+ jobs and 5,000+ members
- [ ] Full async flow works: member applies → Kafka → notification appears in browser
- [ ] AI flow works: recruiter requests shortlist → AI processes → approve/reject in UI
- [ ] All 7 dashboard charts display real data (not zeroes)
- [ ] JMeter ran 4 configurations, bar charts visible in AnalyticsPage
- [ ] All 6 exception cases tested and return correct errors
- [ ] All services deployed to AWS and accessible via public URLs
- [ ] `/ops/cache-stats` shows Redis hit rate > 0 after warm-up
- [ ] Kafka topic list shows all 30 topics created
- [ ] AI evaluation metrics endpoint returns real data
- [ ] `docs/PERFORMANCE_ANALYSIS.md` written

---

*Document version: 2026-05-01 | Based on Class_Project_Description_LinkedIn_AgenticAI.docx + Project/ codebase audit*

---

---

## PART 3 — INTEGRATION RULES (Everyone Must Follow)

> These rules are derived from the actual codebase. They are not suggestions.
> If you break any rule, your code will not integrate with the rest of the team's work.
> Read this entire section before writing a single line.

---

### 3.1 Port Map — Never Change These

| Service | Local Port | Docker Service Name | Frontend Env Var |
|---|---|---|---|
| auth_service | **8001** | `auth_service` | `REACT_APP_AUTH_URL` |
| member_profile_service | **8002** | `member_profile_service` | `REACT_APP_MEMBER_URL` |
| recruiter_company_service | **8003** | `recruiter_company_service` | `REACT_APP_RECRUITER_URL` |
| jobs_service | **8004** | `jobs_service` | `REACT_APP_JOB_URL` |
| applications_service | **8005** | `applications_service` | `REACT_APP_APP_URL` |
| messaging_connections_service | **8006** | `messaging_connections_service` | `REACT_APP_MSG_URL` |
| analytics_service | **8007** | `analytics_service` | `REACT_APP_ANALYTICS_URL` |
| ai_orchestrator_service | **8008** | `ai_orchestrator_service` | `REACT_APP_AI_URL` |
| React frontend | **5173** | `frontend` | — |
| MySQL | **3306** | `mysql` | — |
| MongoDB | **27017** | `mongo` | — |
| Redis | **6379** | `redis` | — |
| Kafka | **9092** | `kafka` | — |
| MinIO API | **9000** | `minio` | — |
| MinIO Console | **9001** | `minio` | — |
| Prometheus | **9090** | `prometheus` | — |
| Grafana | **3000** | `grafana` | — |
| Loki | **3100** | `loki` | — |

**Rules:**
- Never bind a new service to any of these ports.
- Inside Docker Compose, always use the **Docker service name** as hostname (e.g. `kafka:9092`, `mysql:3306`, `redis:6379`). Never use `localhost` inside a container.
- On your local machine (outside Docker), use `localhost:<port>`.

---

### 3.2 Environment Variables — Required for Every Service

Every backend service reads these from environment. Copy `.env.example` to `.env` and fill in:

```bash
# Kafka
EVENT_BUS_MODE=kafka                          # NEVER change to "memory" outside tests
KAFKA_BOOTSTRAP_SERVERS=kafka:9092            # inside Docker; localhost:9092 if running service natively

# MySQL
MYSQL_HOST=mysql                              # inside Docker; localhost if running natively
MYSQL_PORT=3306
MYSQL_DATABASE=linkedin_sim                   # FIXED — do not create a different DB name
MYSQL_USER=root
MYSQL_PASSWORD=root

# MongoDB
MONGO_URL=mongodb://mongo:27017               # inside Docker; mongodb://localhost:27017 if native
MONGO_DATABASE=linkedin_sim_docs              # FIXED — do not create a different DB name

# Redis
CACHE_MODE=redis                              # NEVER use "memory" outside tests
REDIS_URL=redis://redis:6379/0               # db index 0 always

# Auth (all services need these — they validate tokens offline)
JWT_ISSUER=owner1-auth                        # FIXED
JWT_AUDIENCE=linkedin-clone                   # FIXED
OWNER1_JWKS_URL=http://auth_service:8001/.well-known/jwks.json

# MinIO (media uploads)
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=localhost:9000          # what the browser uses to load media
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET_PROFILE=profile-media           # FIXED bucket name
MINIO_BUCKET_RESUME=resume-media             # FIXED bucket name
MINIO_SECURE=false

# Service identity
SERVICE_NAME=<your_service_name>              # snake_case, matches folder name
APP_VERSION=1.0.0

# AI service only
OPENROUTER_API_KEY=<your_key>
OPENROUTER_MODEL=google/gemini-2.5-flash
AI_KAFKA_CONSUMERS_ENABLED=true
MESSAGING_SERVICE_URL=http://messaging_connections_service:8006
```

**Rules:**
- Do not invent new env var names. If you need a new one, announce it to the team and add it to `.env.example` first.
- `MYSQL_DATABASE` is always `linkedin_sim`. `MONGO_DATABASE` is always `linkedin_sim_docs`. Non-negotiable.
- `EVENT_BUS_MODE=memory` and `CACHE_MODE=memory` are **test-only**. If these are set in any running service, Kafka and Redis are bypassed silently — that is a bug.

---

### 3.3 Running the Stack Locally — One Command

```bash
# First time only
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env if you need AI features

chmod +x scripts/bootstrap_local.sh
./scripts/bootstrap_local.sh
```

That script:
1. Starts all Docker containers
2. Runs MySQL schema migrations
3. Runs MongoDB init
4. Creates all Kafka topics
5. Waits for health checks

**If you want to run ONE service natively** (e.g. you're developing jobs_service and want hot-reload):

```bash
# Start all infra except jobs_service
docker compose up mysql mongo redis kafka minio prometheus grafana -d

# Run jobs_service natively with local env overrides
MYSQL_HOST=localhost KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
REDIS_URL=redis://localhost:6379/0 MONGO_URL=mongodb://localhost:27017 \
OWNER1_JWKS_URL=http://localhost:8001/.well-known/jwks.json \
uvicorn services.jobs_service.app.main:app --host 0.0.0.0 --port 8004 --reload
```

**Rules:**
- Always start infra via Docker Compose even when running a service natively.
- Never start two instances of the same service on the same port.
- Run `python3 -m compileall backend` before committing. If it fails, your code has a syntax error — do not push.

---

### 3.4 API Design Rules

#### 3.4.1 HTTP Method

All business API endpoints use **POST**. No exceptions for domain endpoints.

```
POST /jobs/create        ✅
POST /jobs/get           ✅
POST /jobs/search        ✅
GET  /jobs/search        ❌ — breaks the existing pattern
```

The only `GET` endpoints allowed are:
- `GET /ops/healthz`
- `GET /ops/cache-stats`
- `GET /ops/metrics`
- `GET /ai/tasks` and `GET /ai/tasks/{id}` (already established)
- `GET /ai/analytics/approval-rate` (new, approved)
- `GET /ai/analytics/match-quality` (new, approved)
- WebSocket `ws://...` connections

#### 3.4.2 Request Shape

All POST endpoints accept a flat JSON body. Do not wrap in nested keys:

```json
// ✅ correct
{ "job_id": "abc123", "member_id": "xyz789" }

// ❌ wrong — do not wrap
{ "data": { "job_id": "abc123" } }
```

#### 3.4.3 Required HTTP Headers on Every Request (Backend → Backend or Frontend → Backend)

```
Authorization: Bearer <access_token>    # Required on all protected endpoints
X-Trace-Id: <uuid>                      # Optional but strongly encouraged; propagate it
Idempotency-Key: <uuid>                 # Required on: submit, updateStatus, send, create_task
Content-Type: application/json
```

**Rules:**
- Always pass `Authorization` header. Auth is enforced on every non-ops endpoint via `require_auth()`.
- Always generate and pass `X-Trace-Id` from the frontend at the start of a user action. Reuse the same trace_id across all service calls triggered by that single action.
- Always pass `Idempotency-Key` on write operations that can be retried (submit, send, create). Generate it once per user action with `uuid4()`. Do not regenerate on retry.

#### 3.4.4 Response Shape — Always Use `success()` or `fail()`

Every endpoint must return using the shared helpers in `services.shared.common`:

```python
# Success
return success(data={"job_id": "abc"}, trace=trace)
# Produces: {"success": true, "trace_id": "...", "data": {"job_id": "abc"}}

# Failure
return fail(code="JOB_NOT_FOUND", message="Job not found", trace=trace, status_code=404)
# Produces: {"success": false, "trace_id": "...", "error": {"code": "...", "message": "...", "details": {}, "retryable": false}}
```

**Never return a raw dict or a custom response shape.** Frontend parses `response.data.data` and `response.data.error` — deviating from this breaks the UI.

#### 3.4.5 Frontend API Call Pattern

All frontend calls go through `axios` with the token from `AuthContext`. Follow this exact pattern:

```javascript
import axios from 'axios';
import BASE from '../config/api';

// Always use BASE.<service> — never hardcode localhost:80xx in components
const res = await axios.post(`${BASE.job}/jobs/search`, { keyword, location }, {
  headers: { Authorization: `Bearer ${token}` }
});
// Access data as:
const jobs = res.data.data;       // success payload
const err  = res.data.error;      // failure payload
```

**Rules:**
- Never hardcode `http://localhost:8004` inside a component. Always use `BASE.job` (or equivalent).
- The `BASE` object is in `frontend/src/config/api.js`. Do not create a second config file.
- For WebSocket connections: `const ws = new WebSocket(BASE.ai.replace('http', 'ws') + '/ws/ai/tasks/' + taskId)`.

---

### 3.5 CORS Rules

Every backend service has an identical CORS middleware in `app/middleware/cors.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

**Rules:**
- Do not change `allow_origins`. The frontend always runs on port 5173.
- Do not add a wildcard `"*"` to `allow_origins` — it breaks `allow_credentials=True` (browser will reject it).
- If you deploy to AWS and need a custom domain, add it to the list — but also keep the localhost entries for local dev.
- Every new service you create must call `setup_cors(app)` in its `main.py` before including any router.
- `allow_credentials=True` is required because the frontend sends the `Authorization` header (a non-simple header that triggers CORS preflight).

---

### 3.6 Authentication Rules

- **Auth is handled by `auth_service` only.** No other service issues tokens.
- All other services validate tokens **offline** using the public JWKS from `auth_service`.
- Use `require_auth(authorization)` from `services.shared.common` in every route. It returns the decoded JWT claims dict or raises a 401.
- The token contains: `user_id`, `sub`, `role` (member | recruiter | admin), `email`, `first_name`, `last_name`.
- Token lifespan: access token = 15 min, refresh token = 7 days. The frontend `AuthContext` handles auto-refresh transparently.
- **Never trust** `member_id` or `recruiter_id` from the request body alone. Always cross-check with `actor["user_id"]` from the token.

```python
# Every protected route handler looks like this:
async def my_endpoint(payload: dict = Body(...), authorization: str | None = Header(None), ...):
    actor = require_auth(authorization)          # raises 401 if invalid
    member_id = actor["user_id"]                 # use this, not payload.get("member_id")
```

---

### 3.7 Kafka Rules

#### 3.7.1 Envelope — All Kafka Messages Must Use This Exact Shape

Use `build_event()` from `services.shared.common`. Never publish a raw dict to Kafka.

```python
from services.shared.common import build_event
from services.shared.kafka_bus import publish_event

event = build_event(
    event_type="application.submitted",   # must match topic name or be derivable from it
    actor_id=member_id,
    entity_type="application",
    entity_id=application_id,
    payload={"job_id": job_id, "resume_ref": resume_ref},
    trace=trace,
    idempotency_key=idempotency_key,
)
await publish_event("application.submitted", event)
```

The resulting envelope matches the spec exactly:
```json
{
  "event_type": "application.submitted",
  "trace_id": "uuid",
  "timestamp": "ISO-8601",
  "actor_id": "member_id",
  "entity": {"entity_type": "application", "entity_id": "app_id"},
  "payload": {"job_id": "...", "resume_ref": "..."},
  "idempotency_key": "uuid-or-hash",
  "service": "applications_service"
}
```

#### 3.7.2 Topic Naming — Use Existing Topics Only

Do not create new Kafka topics without updating `scripts/create_kafka_topics.sh` and announcing to the team.

Existing topics (all 30 are already created by the bootstrap script):
```
user.created, member.created, member.updated, member.deleted,
member.update.requested, member.media.uploaded, profile.viewed,
job.create.requested, job.update.requested, job.close.requested,
job.save.requested, job.unsave.requested,
job.created, job.viewed, job.updated, job.closed, job.saved,
application.started, application.submitted, application.status.updated, application.note.added,
thread.opened, message.sent,
connection.requested, connection.accepted, connection.rejected, connection.withdrawn,
analytics.normalized, benchmark.completed,
ai.requests, ai.results, ai.rejected
```

#### 3.7.3 Consumer Group Naming

Each service uses exactly one consumer group per service, named after the service:

```python
# ✅ correct
await consume_forever(["application.submitted"], group_id="analytics_service", ...)

# ❌ wrong — don't invent group names
await consume_forever(["application.submitted"], group_id="my_new_consumer", ...)
```

Established consumer groups:
| Group ID | Service | Consumes |
|---|---|---|
| `analytics_service` | analytics_service | job.*, application.*, message.sent, connection.*, profile.viewed, ai.results, benchmark.completed |
| `member_profile_service` | member_profile_service | connection.*, message.sent, member.media.uploaded |
| `ai_orchestrator_service` | ai_orchestrator_service | ai.requests, ai.results |

#### 3.7.4 Idempotency in Consumers

Every Kafka consumer **must** check idempotency before writing to the DB. Use the `idempotency_key` from the event envelope. If you've already processed this key, return immediately. This is what makes consumers safe for at-least-once delivery.

```python
# Pattern inside a consumer callback:
async def handle_event(event: dict):
    key = event.get("idempotency_key")
    if key and already_processed(key):   # check your ledger/DB
        return                            # skip — already done
    # ... do the work
    mark_processed(key)                   # record it
```

---

### 3.8 Database Rules

#### 3.8.1 Which DB for What

| Data Type | Use MySQL | Use MongoDB |
|---|---|---|
| User accounts, tokens | ✅ | |
| Member profiles, recruiters, companies | ✅ | |
| Jobs, saved jobs | ✅ | |
| Applications, notes | ✅ | |
| Outbox events (transactional services) | ✅ | |
| Messages, threads | | ✅ |
| Connection graph, requests | | ✅ |
| Notifications | | ✅ |
| Analytics events, rollups | | ✅ |
| AI task documents | | ✅ |
| Document outbox (messaging, AI) | | ✅ |

**Rule: If your data has a foreign-key-like relationship or needs uniqueness enforcement (duplicate prevention), use MySQL. If it's append-heavy, schema-flexible, or a read projection, use MongoDB.**

#### 3.8.2 MySQL Access

Use `services.shared.repositories` — never write raw SQL in a route or service class. The repository layer handles connection pooling and named parameters.

```python
from services.shared.repositories import JobRepository

repo = JobRepository()
job = repo.get_by_id(job_id)       # returns dict or None
repo.insert(job_dict)
repo.update(job_id, update_dict)
```

#### 3.8.3 Schema Changes

If you need to add a column or table:
1. Create a new migration file: `infra/mysql/00N_description.sql`
2. Use `IF NOT EXISTS` / `IF @exists` guards so it is re-runnable
3. Announce to the team and update `scripts/apply_mysql_schema.sh` if needed
4. Never modify existing migration files — only add new ones

#### 3.8.4 MongoDB Access

Use `services.shared.repositories` for MongoDB collections too. Collection names are fixed:

| Collection | Purpose |
|---|---|
| `threads` | Message threads |
| `messages` | Individual messages |
| `connection_requests` | Connection request documents |
| `connection_graph_docs` | Accepted connection lists per user |
| `notifications` | Member notification inbox |
| `analytics_events` | Raw event log |
| `events_rollup` | Materialized aggregates |
| `ai_tasks` | AI task state and outputs |
| `outbox_documents` | Document outbox (messaging, AI) |

Do not create new collection names without announcing to the team.

---

### 3.9 Redis Caching Rules

Cache keys follow a strict namespace pattern. Never invent free-form keys.

```
job:detail:{job_id}              → jobs_service
jobs:search:{hash}               → jobs_service
jobs:recruiter:{recruiter_id}:*  → jobs_service
jobs:pending:*                   → jobs_service (optimistic pending state)
ai:task:{task_id}                → ai_orchestrator_service
analytics:{endpoint}:{hash}      → analytics_service
unread:{user_id}                 → messaging_connections_service
auth:ratelimit:{email}           → auth_service
```

**Rules:**
- Always use `get_json` / `set_json` / `delete_key` / `delete_pattern` from `services.shared.cache`. Never use the raw Redis client directly.
- Always set a TTL. Never cache without expiry. Default TTLs in jobs_service: job detail = 120s, search = 90s.
- Invalidate on write: when you update or delete an entity, call `delete_pattern` for that entity's cache keys immediately. Do not wait for TTL expiry.
- Caching is transparent — if Redis is down, the service falls back to DB. Do not let cache failures crash a request.

---

### 3.10 Response Status Codes

Use these consistently. Do not use other codes for these situations:

| Situation | HTTP Code | `fail()` code string |
|---|---|---|
| Success | 200 | — |
| Accepted async (Kafka-first) | 202 | — |
| Bad request / missing fields | 400 | `INVALID_REQUEST` |
| Invalid or missing token | 401 | `UNAUTHORIZED` |
| Valid token, wrong role | 403 | `FORBIDDEN` |
| Entity not found | 404 | `NOT_FOUND` |
| Conflict (duplicate) | 409 | `DUPLICATE_*` (e.g. `DUPLICATE_EMAIL`, `DUPLICATE_APPLICATION`) |
| Closed / terminal state | 422 | `JOB_CLOSED`, `APPLICATION_TERMINAL` |
| Internal server error | 500 | `INTERNAL_ERROR` |

---

### 3.11 Naming Conventions

#### Python (backend)
```
Files:           snake_case.py
Classes:         PascalCase
Functions:       snake_case
Variables:       snake_case
Constants:       UPPER_SNAKE_CASE
DB columns:      snake_case   (member_id, job_id, created_at)
Kafka topics:    dot.separated.lowercase   (application.submitted)
Consumer groups: snake_case matching service name
```

#### JavaScript (frontend)
```
Files:           PascalCase.jsx for components and pages
Variables:       camelCase
Constants:       UPPER_SNAKE_CASE
API base keys:   lowercase  (BASE.job, BASE.member, BASE.ai)
```

#### IDs
All entity IDs are **32-character hex strings** (UUID without dashes): `uuid4().hex`.
```python
from uuid import uuid4
job_id = uuid4().hex    # ✅  "a3f9c2b1d4e5..."
job_id = str(uuid4())   # ❌  "a3f9c2b1-d4e5-..." — dashes cause mismatches
```

---

### 3.12 Service-to-Service Calls

When one backend service calls another backend service (e.g., AI service calling jobs_service to fetch a job), always:

1. Use the Docker service name as hostname, not `localhost`.
2. Pass the original `trace_id` in the `X-Trace-Id` header.
3. Pass the original `Authorization` header from the user's request.

```python
import httpx

async def fetch_job(job_id: str, trace: str, auth: str) -> dict | None:
    url = f"{os.environ['JOB_SERVICE_URL']}/jobs/get"  # env var, not hardcoded
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json={"job_id": job_id},
                                headers={"Authorization": auth,
                                         "X-Trace-Id": trace})
    if res.status_code == 200:
        return res.json()["data"]
    return None
```

Service-to-service base URLs (set via env vars already in docker-compose):
```
JOB_SERVICE_URL         = http://jobs_service:8004
APP_SERVICE_URL         = http://applications_service:8005
MESSAGING_SERVICE_URL   = http://messaging_connections_service:8006
MEMBER_SERVICE_URL      = http://member_profile_service:8002
```

---

### 3.13 Ops Endpoints — Every Service Must Expose These

These three endpoints are already wired by `attach_observability()` from `services.shared.observability`. Do not remove them:

```
GET /ops/healthz       → {"status": "ok", "service": "...", "version": "..."}
GET /ops/cache-stats   → {"lookups": n, "hits": n, "misses": n, "hit_rate": 0.xx}
GET /ops/metrics       → Prometheus text format
```

Docker Compose health checks ping `/ops/healthz`. If you break this endpoint, no downstream service will start (all `depends_on` conditions fail).

---

### 3.14 What NOT to Do — Common Mistakes to Avoid

| Don't | Why |
|---|---|
| `EVENT_BUS_MODE=memory` in a running service | Silently bypasses Kafka — analytics and notifications stop working |
| `CACHE_MODE=memory` in a running service | Silently bypasses Redis — cache-stats shows nothing |
| Use `localhost` inside a Docker container | Containers can't reach each other that way — use service names |
| Return a raw `dict` from a route | Bypasses `success()`/`fail()` — frontend JSON parsing breaks |
| Use `GET` for a domain operation | Every domain endpoint is `POST` — only ops endpoints use `GET` |
| Hardcode `http://localhost:8004` in frontend component | Breaks Docker and AWS — use `BASE.job` from config/api.js |
| Create a new Kafka topic without updating `create_kafka_topics.sh` | Topic won't exist in other team members' environments |
| Add a new DB column without a migration file | Column won't exist when team pulls and runs the stack |
| Use `str(uuid4())` for IDs | Dashes in UUIDs break 32-char VARCHAR(32) columns |
| Set `allow_origins=["*"]` with `allow_credentials=True` | Browser rejects this combination for credentialed requests |
| Skip `idempotency_key` on a retry-able write | Causes duplicate DB records on Kafka retry |
| Write to `services.shared.persist` | Deprecated — raises loudly on import. Use `services.shared.repositories` |

---

### 3.15 Git Workflow Rules

```
main branch   = always deployable, always compiles, tests pass
feature branch = your work; name it: <owner_number>/<short_description>
                 e.g.  person1/kafka-first-apply
                        person3/salary-range-filter
```

Before every push:
```bash
python3 -m compileall backend          # must produce no errors
pytest tests/api -q                    # must pass all tests
```

Never push directly to `main`. Create a PR, and at minimum one other person reviews it.

**Merge order matters:** Person 1's infra changes must merge first (schema migrations, Kafka topics) before others build on top.

---

### 3.16 Quick Reference Card (Print This)

```
┌─────────────────────────────────────────────────────────┐
│  LOCAL PORTS                                            │
│  frontend  5173  |  auth  8001  |  member  8002         │
│  recruiter 8003  |  jobs  8004  |  apply   8005         │
│  messaging 8006  |  analytics 8007  |  AI  8008         │
│  mysql 3306  |  mongo 27017  |  redis 6379              │
│  kafka 9092  |  minio 9000   |  grafana 3000            │
├─────────────────────────────────────────────────────────┤
│  DB NAMES                                               │
│  MySQL:   linkedin_sim                                  │
│  MongoDB: linkedin_sim_docs                             │
├─────────────────────────────────────────────────────────┤
│  ALL DOMAIN API ENDPOINTS = POST                        │
│  RESPONSE SHAPE = success(data) / fail(code, msg)       │
│  AUTH HEADER   = Authorization: Bearer <token>          │
│  TRACE HEADER  = X-Trace-Id: <uuid>                     │
│  IDEM  HEADER  = Idempotency-Key: <uuid> (writes only)  │
├─────────────────────────────────────────────────────────┤
│  IDs = uuid4().hex  (32 chars, no dashes)               │
│  CORS origins = localhost:5173 only                     │
│  Inside Docker = use service names, not localhost       │
│  Kafka events = always build_event() + publish_event()  │
│  Redis keys   = always namespaced (entity:type:id)      │
└─────────────────────────────────────────────────────────┘
```

---

*Document version: 2026-05-02 | Integration rules derived from live codebase: docker-compose.yml, .env.example, shared/common.py, shared/kafka_bus.py, middleware/cors.py, config/api.js*
