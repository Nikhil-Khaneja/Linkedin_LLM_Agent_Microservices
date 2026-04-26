# Owner 1 - Auth + API Edge Service

## Scope
This service owns:
- POST /auth/register
- POST /auth/login
- POST /auth/refresh
- POST /auth/logout
- GET /.well-known/jwks.json
- POST /gateway/idempotency/check

## Stack
- FastAPI
- MySQL
- Redis
- JWT (RS256)

## Local setup

### 1. Create venv
```bash
python3 -m venv venv
source venv/bin/activate