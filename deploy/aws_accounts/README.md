# Per-account AWS deployment templates

Each backend owner account deploys its own service. Owner 9 deploys the shared frontend and runs JMeter.

## Account layout

- owner1_auth
- owner2_member
- owner3_recruiter
- owner4_jobs
- owner5_applications
- owner6_messaging
- owner7_analytics
- owner8_ai
- owner9_frontend

## Common EC2 preparation

```bash
sudo dnf update -y || sudo apt-get update -y
sudo dnf install -y docker git || sudo apt-get install -y docker.io git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user || sudo usermod -aG docker ubuntu
newgrp docker
```

## Backend owners 1-8

Copy the service folder, fill `.env.aws`, then run:

```bash
docker compose -f docker-compose.aws.yml --env-file .env.aws up -d --build
```

## Owner 9

Owner 9 deploys the shared frontend and runs JMeter from a separate runner box or CI job.
See `owner9_frontend/README.md` and `docs/owner9_frontend_testing.md`.
