# AWS cross-account validation

Run this before deploy:

```bash
python3 deploy/aws_accounts/validate_multi_account.py --env-dir deploy/aws_accounts/env
```

What it validates:
- every owner account has its own env file
- owner2-owner8 point at Owner 1 JWKS over HTTPS
- owner4-owner8 point at Owner 7 Kafka brokers
- owner9 frontend points at all public service URLs

Recommended deployment order:
1. Owner 7 Kafka/shared analytics
2. Owner 1 auth/JWKS
3. Owners 2-6 backend services
4. Owner 8 AI orchestrator
5. Owner 9 frontend

Recommended manual checks after deploy:
- `curl https://owner1.example.com/.well-known/jwks.json`
- login via Owner 1 and call one protected API in each account
- produce an `application.submitted` event and verify Owner 7 rollups update
- create an AI task and verify `ai.requests` -> `ai.results` flow
