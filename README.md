# Job Service - Owner 4

LinkedIn Simulation + Agentic AI Services - Distributed Systems Project

## Overview

The Job Service handles all job-related operations in the LinkedIn simulation platform:
- Job CRUD operations (create, read, update, close)
- Job search with filters
- Saved jobs management
- Redis caching (cache-aside pattern)
- Kafka event publishing

## Tech Stack

- **Framework**: FastAPI (Python 3.11)
- **Database**: MySQL 8.0
- **Cache**: Redis 7
- **Message Broker**: Kafka (hosted on Owner 7)
- **Containerization**: Docker + Docker Compose

## Quick Start

### 1. Start Services

```bash
# Start MySQL, Redis, and Job Service
docker-compose up -d

# Check logs
docker-compose logs -f job-service
```

### 2. Verify Health

```bash
curl http://localhost:8004/health
```

### 3. Access API Documentation

Open http://localhost:8004/docs in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/jobs/create` | POST | Create job posting |
| `/api/v1/jobs/get` | POST | Get job details |
| `/api/v1/jobs/update` | POST | Update job |
| `/api/v1/jobs/search` | POST | Search jobs |
| `/api/v1/jobs/close` | POST | Close job |
| `/api/v1/jobs/byRecruiter` | POST | List recruiter's jobs |
| `/api/v1/jobs/save` | POST | Save job |
| `/api/v1/jobs/unsave` | POST | Unsave job |
| `/api/v1/jobs/savedByMember` | POST | List saved jobs |
| `/api/v1/jobs/status` | POST | Get job status (internal) |

## Kafka Topics

| Topic | Description |
|-------|-------------|
| `job.created` | New job created |
| `job.updated` | Job updated |
| `job.closed` | Job closed (Owner 5 consumes this) |
| `job.viewed` | Job viewed |
| `job.saved` | Job saved |

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key variables:
- `DATABASE_HOST` - MySQL host
- `REDIS_HOST` - Redis host
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka broker (Owner 7)
- `JWKS_URL` - JWT validation endpoint (Owner 1)

## Development

### Run Locally (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start MySQL and Redis separately
# Then run:
uvicorn src.main:app --reload --port 8004
```

### Run Tests

```bash
pytest tests/ -v
```

## Project Structure

```
job-service/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── src/
│   ├── main.py              # FastAPI application
│   ├── config/              # Configuration
│   │   ├── settings.py
│   │   ├── database.py
│   │   ├── redis_config.py
│   │   └── kafka_config.py
│   ├── models/              # Pydantic schemas
│   │   └── schemas.py
│   ├── routes/              # API routes
│   │   └── jobs.py
│   └── services/            # Business logic
│       └── job_service.py
├── sql/
│   ├── schema.sql           # Database schema
│   └── seed_data.sql        # Sample data
└── tests/
    └── test_api.py
```

## Owner 4 Responsibilities

1. **Week 1**: EC2 setup, database schema, API contract
2. **Week 2**: Implement all CRUD endpoints with Redis caching
3. **Week 3**: Kafka integration - publish job events
4. **Week 4**: Benchmark Scenario A (job search + detail)

## Coordination

- **Owner 1**: Get JWKS endpoint for JWT validation
- **Owner 5**: Consumes `job.closed` events
- **Owner 7**: Kafka broker + analytics
- **Owner 8**: AI agent consumes job data


