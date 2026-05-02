# Local and AWS Run Guide

## Local run

```bash
cp .env.example .env
chmod +x scripts/bootstrap_local.sh
./scripts/bootstrap_local.sh
```

This starts:
- MySQL
- MongoDB
- Redis
- Kafka KRaft
- Owner 1-8 services
- Prometheus
- Grafana
- Frontend

## Local URLs

- Frontend: `http://localhost:5173`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`

## Multi-account AWS pattern

- Owners 1-8 deploy their own backend service in their own AWS account
- Owner 7 hosts shared Kafka and analytics persistence
- Owner 9 deploys the shared frontend and runs JMeter against the public URLs

## Recommended AWS order

1. Deploy Owner 7 Kafka + analytics infra
2. Deploy Owner 1 auth/JWKS
3. Deploy Owners 2-6 backend services
4. Deploy Owner 8 AI service
5. Deploy Owner 9 frontend
6. Run JMeter and upload benchmark results

## EC2 deployment pattern

Each owner account uses:
- one EC2 instance
- Docker + Docker Compose
- security group exposing only required service ports
- SSM Parameter Store or `.env` file for config

## Service health validation

After deployment, verify:
- `/ops/healthz`
- `/docs`
- `/ops/cache-stats`
- `/ops/metrics`

## Owner 9 frontend validation

- login flow works
- job search works
- apply flow works
- messaging flow works
- AI workflow reaches waiting-for-approval state
- Grafana dashboard shows request traffic and cache metrics


## Auth/JWKS across separate AWS accounts

Each backend service must be configured with the public Owner 1 JWKS URL via `OWNER1_JWKS_URL`.
Owner 1 is the trust anchor for bearer auth; all other services validate JWTs offline using the cached JWKS response.
In local Docker mode, the default is `http://auth_service:8001/.well-known/jwks.json`.
In cross-account AWS mode, point this to the public HTTPS URL for the Owner 1 deployment.


## OpenRouter and AWS deployment

Set the following environment variables for the `ai_orchestrator_service` in local Docker Compose or AWS ECS task definitions:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL=google/gemini-2.5-flash`
- `PUBLIC_BASE_URL=https://<your-public-api-domain>`

`PUBLIC_BASE_URL` should point to your public load balancer or API domain so the AI service can generate environment-correct URLs.
