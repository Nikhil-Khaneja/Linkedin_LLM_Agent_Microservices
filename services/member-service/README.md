# Owner 2 — Member Profile Service
### LinkedIn Simulation + Agentic AI | Distributed Systems | SJSU Group 2

---

## Overview

Owner 2 is the **Member Profile Service** — responsible for all member profile operations in the LinkedIn simulation. This includes creating profiles, updating them, searching via Elasticsearch, and caching with Redis.

---

## Files in This Repo

```
owner2-member-service/
├── services/member-service/        ← Backend (Node.js)
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── index.js                ← Main entry point (port 3002)
│       ├── routes/members.js       ← All 5 API endpoints
│       ├── db/
│       │   ├── mysql.js            ← MySQL connection pool
│       │   ├── redis.js            ← Redis cache client
│       │   └── elasticsearch.js    ← Elasticsearch client
│       ├── kafka/producer.js       ← Kafka event publisher
│       ├── middleware/
│       │   ├── auth.js             ← JWT Bearer verification via JWKS
│       │   └── errorHandler.js     ← Global error handler
│       ├── search/memberSearch.js  ← Elasticsearch search logic
│       └── swagger.js              ← Swagger API docs
│
├── frontend/src/pages/
│   └── ProfilePage.jsx             ← React profile page (Frontend)
│
├── migrations/001_init.sql         ← MySQL schema
├── seed/seed.sql                   ← Test data
├── tests/test_members.py           ← Pytest test suite
└── benchmark/member_benchmark.js   ← k6 benchmark script
```

---

## API Endpoints

| Method | Endpoint | Description | Auth | Cache | Kafka |
|--------|----------|-------------|------|-------|-------|
| GET | `/health` | Health check | ❌ | — | — |
| POST | `/members/create` | Create member profile | ✅ JWT | — | `member.created` |
| POST | `/members/get` | Get profile | ✅ JWT | Redis 300s | — |
| POST | `/members/update` | Update profile | ✅ JWT | Invalidate | — |
| POST | `/members/delete` | Soft delete | ✅ JWT | Invalidate | — |
| POST | `/members/search` | Search members | ✅ JWT | — | — |

**Swagger UI:** `http://localhost:3002/api-docs`

---

## Tech Stack

| Tech | Purpose |
|------|---------|
| Node.js + Express | REST API server |
| MySQL | Member data storage (23 tables) |
| Redis | Profile caching (300s TTL) |
| Elasticsearch | Full-text member search |
| Kafka | Event publishing (member.created) |
| JWT RS256 + JWKS | Authentication via Owner 1 |
| Swagger UI | API documentation |

---

## How to Run (Full Project)

```bash
# Clone full project
cd linkedin-final

# Start all services
docker compose up -d --build

# Seed data
python3 scripts/seed_data.py

# Open Swagger
open http://localhost:3002/api-docs
```

**Login credentials:**
- Member: `ava.shah@example.com` / `StrongPass#1`

---

## Key Implementation Details

### 1. Redis Caching
```javascript
// Cache key: member:{member_id}
// TTL: 300 seconds
const cached = await redis.get('member:' + member_id);
if (cached) return res.json({ data: JSON.parse(cached), meta: { cache: 'hit' } });
// Cache miss → query MySQL → store in Redis
await redis.set(cacheKey, JSON.stringify(result), 'EX', 300);
```

### 2. Elasticsearch Search
```javascript
// Full-text search on name, headline, skills
const { members, source } = await searchMembers({ keyword, location, skill });
// Falls back to MySQL LIKE search if ES unavailable
```

### 3. Kafka Event
```javascript
// Published on every member.create
await publishEvent('member.created', {
  event_type: 'member.created',
  trace_id: req.traceId,
  timestamp: new Date().toISOString(),
  actor_id: req.user.userId,
  entity: { entity_type: 'member', entity_id: memberId },
  payload: { member_id: memberId },
  idempotency_key: uuidv4()
});
```

### 4. JWT Auth via JWKS
```javascript
// Verifies token using Owner 1's public key
// http://auth-service:3001/.well-known/jwks.json
const requireAuth = async (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];
  // Verify RS256 signature via JWKS
}
```

---

## Frontend (ProfilePage.jsx)

**Location:** `frontend/src/pages/ProfilePage.jsx`

**Features:**
- View member profile (name, headline, city, skills)
- Edit profile inline
- Upload profile photo (resize to 200x200)
- Add/remove skills
- Add experience and education
- View profile stats (views, applications)

**Access:** `http://localhost:3000` → Login → Click **Me** → **View full profile**

---

## Database Schema (MySQL)

```sql
-- Members table
CREATE TABLE members (
    member_id       VARCHAR(32) PRIMARY KEY,
    user_id         VARCHAR(32) NOT NULL,
    first_name      VARCHAR(64) NOT NULL,
    last_name       VARCHAR(64) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    city            VARCHAR(64),
    state           VARCHAR(64),
    country         VARCHAR(64) DEFAULT 'USA',
    headline        VARCHAR(255),
    resume_text     TEXT,
    is_deleted      TINYINT(1) DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Related tables
-- member_skills (member_id, skill_name, proficiency)
-- member_experience (member_id, company_name, title, dates)
-- member_education (member_id, institution, degree, years)
```

---

## How to Run Tests

```bash
# Install pytest
pip3 install requests pytest

# Start full project first
cd linkedin-final
docker compose up -d

# Run tests
pytest tests/test_members.py -v
```

---

## Benchmark Results (Scenario A — Member Search)

| Config | Avg Latency | P95 | Throughput | Errors |
|--------|------------|-----|------------|--------|
| B (MySQL only) | ~120ms | ~310ms | ~42 req/s | ~2% |
| B+S (+ Redis) | ~68ms | ~155ms | ~88 req/s | ~1.2% |
| B+S+K (+ Kafka) | ~74ms | ~170ms | ~95 req/s | ~1% |
| Optimized | ~45ms | ~98ms | ~152 req/s | ~0.6% |

---

## Project Context

| Owner | Service | Port |
|-------|---------|------|
| Owner 1 | Auth + API Edge | 3001 |
| **Owner 2** | **Member Profile (this repo)** | **3002** |
| Owner 3 | Recruiter & Company | 3003 |
| Owner 4 | Job Service | 3004 |
| Owner 5 | Application Service | 3005 |
| Owner 6 | Messaging + Connections | 3006 |
| Owner 7 | Analytics + Logging | 3007 |
| Owner 8 | AI Agent Orchestrator | 8000 |
