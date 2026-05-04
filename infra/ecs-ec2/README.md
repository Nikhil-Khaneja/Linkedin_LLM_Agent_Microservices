# ECS on EC2 (bridge networking) + GitHub Actions

Deploy the LinkedIn-sim stack on **EC2** (not Fargate) using **multiple ECS services** so each app can roll **independently**. Each Python service has its **own ECR image** (multi-stage `backend/Dockerfile` targets) so CI can rebuild and redeploy only the services you select. Each task uses **bridge** networking on the shared container instance; the **platform** task publishes MySQL, MongoDB, Redis, Kafka, and MinIO on **host ports**, and app tasks talk to them via the instance **private IP** (`ECS_HOST_PRIVATE_IP`). Infrastructure is created with **AWS CLI** only (no Terraform).

## Overview

- **Bootstrap** (`bootstrap.sh`): IAM (including GitHub OIDC deploy role), ECR repos, ECS cluster, CloudWatch log group, security group (public + self-referencing for intra-host ports), ECS-optimized EC2 instance with host paths under `/ecs/linkedin-sim/*`.
- **Render** (`render_taskdefs.py`): splits `ecs-taskdef.template.json` into `rendered/taskdef-*.json` plus `services.manifest.json` (one ECS service per app + `linkedin-sim-platform` for data).
- **Deploy** (`deploy_services.py`): registers selected task definitions and creates/updates only the matching ECS services, then waits for stability (platform first when it is in the batch). **Routine deploys use `ALL_APPS`** (every app + frontend, **not** the data-plane task) so MySQL/Mongo/Redis/Kafka/MinIO are **not** bounced unless you opt in or the platform service is missing/inactive.
- **CI/CD** (`.github/workflows/deploy-ecs-ec2.yml`): OIDC → build/push images → `render_taskdefs.py` → `deploy_services.py`. On **push**, path filters choose services; **`ALL_WITH_PLATFORM`** (or including `linkedin-sim-platform`) is required to roll the data plane. **Manual runs** default to apps-only unless you enable **Redeploy data plane**.
- **Destroy** (`destroy.sh`): deletes all `linkedin-sim-*` ECS services, terminates tagged EC2, deletes cluster; optional `--delete-ecr`.

## Prerequisites

- AWS account and CLI configured locally for bootstrap (`aws configure` or env vars).
- Tools:

```bash
aws --version
docker --version
git --version
python3 --version
curl --version
```

## One-time AWS bootstrap

Set variables and run (replace owner/repo). **You do not need an existing EC2 key pair:** if you omit `KEY_NAME`, bootstrap uses **`linkedin-sim-key`**, creates that key pair in EC2 when missing, and writes **`linkedin-sim-key.pem`** under the repo root (keep it safe). Only set `KEY_NAME` if you want to reuse a key pair name you already have in that region.

```bash
export AWS_REGION=us-east-1
export PROJECT=linkedin-sim
export CLUSTER=linkedin-sim-ec2
# optional: export KEY_NAME=my-existing-keypair
# optional: export INSTANCE_TYPE=t3.large   # cheaper; default t3.xlarge is safer (memory for Kafka+DB+8 apps)
export GITHUB_OWNER=your-github-username-or-org
export GITHUB_REPO=Linkedin_Prototype_LLM_Agent_Microservices

bash infra/ecs-ec2/bootstrap.sh
```

Save the printed **`.pem`** path and the **GitHub variable** lines.

Bootstrap does **not** create ECS services; the first workflow run creates **one ECS service per entry** in `services.manifest.json` (EC2 launch type).

## GitHub repository variables

Add these in **Settings → Secrets and variables → Actions → Variables**:

| Name | Example / source |
|------|------------------|
| `AWS_REGION` | Same as bootstrap |
| `AWS_ROLE_ARN` | `GITHUB_ACTIONS_ROLE_ARN` from bootstrap output |
| `ECS_CLUSTER` | `linkedin-sim-ec2` |
| `APP_HOST` | **Canonical browser host** (domain or Elastic IP). Optional comma list, e.g. `thelastdegree.dev,34.199.109.255` — first entry is used for public URLs in task env; **all** entries are allowed CORS origins. |
| `ECS_HOST_PRIVATE_IP` | EC2 **private** IP (printed as `ECS_HOST_PRIVATE_IP` from bootstrap) |
| `ECR_FRONTEND_REPOSITORY` | `linkedin-sim/frontend` |
| `ECR_MYSQL_REPOSITORY` | `linkedin-sim/mysql` |
| `ECR_MONGO_REPOSITORY` | `linkedin-sim/mongo` |
| `PUBLIC_HTTP_SCHEME` | Optional. Affects **`PUBLIC_BASE_URL`** in rendered task defs (and related “canonical” links). **APIs and media on `:8001`–`:8008` stay `http://`** until you put TLS in front of those ports or route them behind **443**. Defaults to `http`. |

Backend Python services use **eight separate ECR repositories** created by `bootstrap.sh`: `linkedin-sim/auth_service`, `linkedin-sim/member_profile_service`, … (see `bootstrap.sh`). CI builds with `docker build --target <service> ./backend` and does **not** use a single `linkedin-sim/backend` repository anymore.

### If you already used the old single `linkedin-sim/backend` repo

1. Re-run **`bash infra/ecs-ec2/bootstrap.sh`** (same env as before) so the eight per-service ECR repos exist.
2. In GitHub Actions variables, **remove `ECR_BACKEND_REPOSITORY`** if present; CI no longer reads it.
3. Run a deploy (push to `main` or **workflow_dispatch**). After it succeeds, you can delete the legacy **`linkedin-sim/backend`** ECR repository in the AWS console (optional).

### HTTPS (`https://your-domain`)

Browsers **block mixed content**: if the UI loads over **HTTPS**, API calls must use **HTTPS** too (not `http://…:8001`).

1. **Terminate TLS** in front of the EC2 instance, e.g. **Application Load Balancer + ACM certificate**, **Cloudflare**, or **Caddy/nginx + Let’s Encrypt** on the host. You must expose **TLS on the same hostnames/ports** the React app calls (today that is **port 80** for the UI and **8001–8008** for APIs), or put a **reverse proxy** on **443** that routes to those ports and then point the app at **HTTPS URLs** only.
2. In GitHub Actions **Variables**, set **`PUBLIC_HTTP_SCHEME`** to **`https`** and keep **`APP_HOST`** as your public hostname (comma-list domain + IP if needed). Redeploy so `render_taskdefs.py` updates **`PUBLIC_BASE_URL`** and CORS. **`MEMBER_PUBLIC_URL`** and the default frontend `api.js` bases for **`:8001`–`:8008`** remain **`http://`** until each port (or a single **443** proxy path) actually serves TLS—otherwise resume/media links hit **`ERR_SSL_PROTOCOL_ERROR`**.
3. Open the site only over **`https://`** once step 1 is working end-to-end.

Until TLS works on those endpoints, use **`http://`** for both the domain and APIs, or the browser will block requests.

### Local verification (no AWS)

From the repo root:

```bash
make verify-ecs-ec2
# or: ./scripts/verify_ecs_ec2_local.sh
```

## GitHub repository secret (OpenRouter / AI)

The deploy workflow passes this into `render_taskdefs.py`, which bakes it into the **AI orchestrator** task environment on ECS.

1. GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret** (use **Secrets**, not Variables — the key must not appear in logs).
2. Name: **`OPENROUTER_API_KEY`**
3. Value: your key from [OpenRouter](https://openrouter.ai/) (typically starts with `sk-or-`).

After saving the secret, **run the deploy workflow again** (or push a change under `backend/services/ai_orchestrator_service/**`) so **`linkedin-sim-ai-orchestrator`** gets a new task definition with the key. Variables alone do not inject this; it must be a **secret**.

## First deployment

After variables (and optionally the secret above) are set:

- Push to `main`, or  
- **Actions → Deploy ECS EC2 → Run workflow** (leave **Redeploy data plane** unchecked: the deploy script still creates `linkedin-sim-platform` if that service is missing or inactive, then rolls the apps.)

To **intentionally** rebuild and restart MySQL/Mongo/Redis/Kafka/MinIO (e.g. after changing `infra/mysql/**` or the data Dockerfiles), either enable **Redeploy data plane** on the manual workflow, or push a change that matches the `platform_data` path filter so CI adds `linkedin-sim-platform` to the selection.

## Verify deployment

```bash
curl "http://<APP_HOST>:8001/ops/healthz"
curl "http://<APP_HOST>:8002/ops/healthz"
curl "http://<APP_HOST>:8003/ops/healthz"
curl "http://<APP_HOST>:8004/ops/healthz"
curl "http://<APP_HOST>:8005/ops/healthz"
curl "http://<APP_HOST>:8006/ops/healthz"
curl "http://<APP_HOST>:8007/ops/healthz"
curl "http://<APP_HOST>:8008/ops/healthz"
```

- **Frontend:** `http://<APP_HOST>`
- **MinIO console:** `http://<APP_HOST>:9001`

## Logs

```bash
aws logs tail /ecs/linkedin-sim --since 30m --follow --region <AWS_REGION>
```

## Redeploy / partial rollouts

- **`ALL_APPS`** (default on push when a broad change is detected, and default on manual workflow): rolls **every application service + the frontend** only. **Does not** restart **`linkedin-sim-platform`** (data plane) if it is already active—this avoids wiping or bouncing databases on unrelated CI runs.
- **`ALL_WITH_PLATFORM`**: rolls **including** the data-plane task (MySQL, Mongo, Redis, Kafka, MinIO). Use the manual workflow checkbox **Redeploy data plane**, set `DEPLOY_SELECTION=ALL_WITH_PLATFORM` locally, or let CI add `linkedin-sim-platform` when **`platform_data`** paths change (`infra/mysql/**`, `infra/mongo/**`, `Dockerfile.mysql` / `Dockerfile.mongo`).
- **Push to `main`**: path filters map changed paths → **only** the affected ECS services (e.g. only `linkedin-sim-auth` when `backend/services/auth_service/**` changes). Changes to **`ecs-taskdef.template.json`** or **`render_taskdefs.py`** trigger **`ALL_APPS`** (every app + frontend, still **not** the data plane unless `platform_data` matches). Shared backend image inputs (`backend/services/shared/**`, `backend/Dockerfile`, `backend/requirements.txt`) roll **all eight backend** ECS services **without** restarting the **frontend** unless `frontend/**` also changed. Edits to **`deploy_services.py` alone** do **not** trigger an ECS rollout (no task-definition or image change). **Commits that touch none of the filtered paths** skip build and deploy entirely—use **workflow_dispatch** when you need a rollout without a matching code path.
- **Legacy `DEPLOY_SELECTION=ALL`**: treated like **`ALL_APPS`** (apps + frontend only). Use **`ALL_WITH_PLATFORM`** when you truly need a full stack rollout including databases.

## Destroy

```bash
export AWS_REGION=us-east-1
export CLUSTER=linkedin-sim-ec2
bash infra/ecs-ec2/destroy.sh
# Optional: also remove ECR repos
bash infra/ecs-ec2/destroy.sh --delete-ecr
```

IAM roles are **not** removed by `destroy.sh`.

## Troubleshooting

### `RunInstances` / “not supported in your requested Availability Zone”

Some instance types (e.g. `m7i-flex.large`) are not offered in every AZ (often **`us-east-1e`** is excluded). **`bootstrap.sh` picks a default-VPC subnet whose AZ supports your `INSTANCE_TYPE`** via `describe-instance-type-offerings`. Re-run bootstrap after pulling the latest script.

### `RunInstances` / “not eligible for Free Tier”

Some accounts (often new or student) can only launch **Free Tier–eligible** instance types until billing / account setup allows paid EC2. **`t3.large` and `t3.xlarge` are not Free Tier** in that mode, so `run-instances` fails with `InvalidParameterCombination` mentioning Free Tier.

**Fix:** In the AWS console, complete **default payment method** and any **account verification**, and use **Billing → Cost Management** to confirm you are allowed to use services beyond strict Free Tier limits. Then rerun bootstrap (same `INSTANCE_TYPE` or default `t3.xlarge`).

To see what your account marks as Free Tier–eligible:

```bash
aws ec2 describe-instance-types --filters Name=free-tier-eligible,Values=true \
  --query 'InstanceTypes[].InstanceType' --output text
```

Using only a tiny eligible type (e.g. `t3.micro`) is **not** realistic for MySQL + Mongo + Kafka + all apps on one host; you need paid capacity for this demo.

If you **must** launch only Free Tier–eligible types, pick the **largest x86** option your account lists (often **`m7i-flex.large`** or **`c7i-flex.large`**) and set `INSTANCE_TYPE` before bootstrap—they still may be tight, but they beat `t3.small` / `t3.micro` on RAM and CPU. **`t4g.*`** is **Graviton (ARM)**; bootstrap now selects the **ARM64 ECS-optimized AMI** for those instance families so `export INSTANCE_TYPE=t4g.small` works. **`t3.*`** continues to use the default **x86_64** ECS AMI.

```bash
aws ecs describe-services --cluster <cluster> --services <service> --region <region>
aws ecs list-tasks --cluster <cluster> --service-name <service> --region <region>
aws ecs describe-tasks --cluster <cluster> --tasks <task-arn> --region <region>
```

- Confirm the EC2 instance is **registered** in the cluster (`ecs:ListContainerInstances`).
- Confirm security group allows **80**, **8001–8008**, **9000–9001** from your client if health checks fail externally.
- MySQL/Mongo images run init scripts on **first** empty data volume only; to re-init, clear host dirs under `/ecs/linkedin-sim/` on the instance (destructive).

## Local acceptance checks (no AWS)

```bash
bash -n infra/ecs-ec2/bootstrap.sh
bash -n infra/ecs-ec2/destroy.sh
python3 -c "import ast; ast.parse(open('infra/ecs-ec2/render_taskdefs.py').read())"
python3 -c "import json; json.load(open('infra/ecs-ec2/ecs-taskdef.template.json')); print('taskdef template OK')"
```

Render smoke test (dummy values):

```bash
export AWS_REGION=us-east-1 AWS_ACCOUNT_ID=123456789012 APP_HOST=1.2.3.4 ECS_HOST_PRIVATE_IP=10.0.0.5
export BACKEND_IMAGE=x/y:a FRONTEND_IMAGE=x/y:a MYSQL_IMAGE=x/y:a MONGO_IMAGE=x/y:a
export OPENROUTER_API_KEY=
python3 infra/ecs-ec2/render_taskdefs.py
grep -q '"networkMode": "bridge"' infra/ecs-ec2/rendered/taskdef-platform.json
```

For CI-style per-service URIs, export `BACKEND_IMAGE_AUTH_SERVICE`, `BACKEND_IMAGE_MEMBER_PROFILE_SERVICE`, … through `BACKEND_IMAGE_AI_ORCHESTRATOR_SERVICE` instead of `BACKEND_IMAGE`.
