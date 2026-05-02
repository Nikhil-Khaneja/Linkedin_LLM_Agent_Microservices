# AWS Multi-Account Deployment Guide

This repo assumes one backend service per AWS account and one shared frontend owner.

## Accounts

- Owner 1 account: Auth + JWKS
- Owner 2 account: Member profile service
- Owner 3 account: Recruiter + company service
- Owner 4 account: Job service
- Owner 5 account: Application service
- Owner 6 account: Messaging + connections service
- Owner 7 account: Kafka + analytics + benchmark persistence
- Owner 8 account: AI orchestrator service
- Owner 9 account: Frontend + JMeter runner

## Network model

The simplest class-demo model is public HTTPS APIs with IP allow lists between accounts.
A more secure variant is private peering and reverse proxy ingress.

## Per-account deliverables

Each owner account should contain:
- one EC2 instance
- Docker Compose for that owner's service
- Redis only where needed locally by the service
- logs forwarded to stdout and optionally CloudWatch
- `/ops` endpoints enabled

## Owner 7 special case

Owner 7 hosts:
- shared Kafka
- analytics service
- benchmark ingestion endpoint

## Owner 9 special case

Owner 9 hosts:
- shared frontend deployment
- JMeter execution box or GitHub Action
- release verification checklist

## Production-hardening checklist

- pin container image versions
- use TLS termination at the reverse proxy
- restrict security groups to known peers
- store secrets in AWS Systems Manager Parameter Store
- enable regular backups for data stores
- monitor p95 latency and cache hit rate in Grafana


## Cross-account auth contract

- Owner 1 exposes a public JWKS endpoint over HTTPS.
- Owners 2-8 set `OWNER1_JWKS_URL` to that URL.
- Owner 9 frontend only talks to public HTTPS APIs and stores the access token returned by Owner 1.
- Kafka bootstrap configuration for cross-account deployments should point to the Owner 7 public/private broker endpoints depending on your network model.
