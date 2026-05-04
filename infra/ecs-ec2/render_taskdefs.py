#!/usr/bin/env python3
"""
Split the monolithic ECS task definition into per-service task defs (bridge, EC2).

Platform task: mysql, mongo, redis, kafka, minio with host port mappings.
Each app + frontend: single-container task. Apps reach data stores via ECS_HOST_PRIVATE_IP.

Reads: infra/ecs-ec2/ecs-taskdef.template.json (source of truth for container specs)
Writes: infra/ecs-ec2/rendered/*.json + infra/ecs-ec2/rendered/services.manifest.json
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SRC = HERE / "ecs-taskdef.template.json"
OUT_DIR = HERE / "rendered"

REQUIRED_COMMON = (
    "AWS_REGION",
    "AWS_ACCOUNT_ID",
    "APP_HOST",
    "ECS_HOST_PRIVATE_IP",
    "FRONTEND_IMAGE",
    "MYSQL_IMAGE",
    "MONGO_IMAGE",
)

# Container names in ecs-taskdef.template.json (must match Dockerfile --target names).
BACKEND_CONTAINERS = (
    "auth_service",
    "recruiter_company_service",
    "member_profile_service",
    "jobs_service",
    "applications_service",
    "messaging_connections_service",
    "analytics_service",
    "ai_orchestrator_service",
)

PLATFORM = {"mysql", "mongo", "redis", "kafka", "minio"}

HOST_PORTS = {
    "mysql": [(3306, 3306)],
    "mongo": [(27017, 27017)],
    "redis": [(6379, 6379)],
    "kafka": [(9092, 9092)],
    "minio": [(9000, 9000), (9001, 9001)],
}


def _replace_placeholders(obj: dict | list | str) -> dict | list | str:
    """Substitute __KEY__ in strings from os.environ."""
    if isinstance(obj, dict):
        return {k: _replace_placeholders(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_placeholders(v) for v in obj]
    if isinstance(obj, str):
        s = obj
        for key in (
            "AWS_REGION",
            "AWS_ACCOUNT_ID",
            "APP_HOST",
            "ECS_HOST_PRIVATE_IP",
            "FRONTEND_IMAGE",
            "MYSQL_IMAGE",
            "MONGO_IMAGE",
            "OPENROUTER_API_KEY",
        ):
            token = f"__{key}__"
            if token in s:
                s = s.replace(token, os.environ.get(key, ""))
        return s
    return obj


def _backend_image_env_key(container_name: str) -> str:
    return f"BACKEND_IMAGE_{container_name.upper()}"


def _backend_image_for(container_name: str) -> str:
    """ECR URI for one Python service. Set per-service env vars, or legacy BACKEND_IMAGE for all."""
    single = (os.environ.get("BACKEND_IMAGE") or "").strip()
    if single:
        return single
    return (os.environ.get(_backend_image_env_key(container_name)) or "").strip()


def _validate_backend_images() -> list[str]:
    missing: list[str] = []
    if (os.environ.get("BACKEND_IMAGE") or "").strip():
        return []
    for name in BACKEND_CONTAINERS:
        if not _backend_image_for(name):
            missing.append(_backend_image_env_key(name))
    return missing


def _slug(container_name: str) -> str:
    if container_name == "frontend":
        return "frontend"
    base = container_name.removesuffix("_service")
    return base.replace("_", "-")


def _service_family(container_name: str) -> str:
    return "linkedin-sim-" + _slug(container_name)


def _service_name(container_name: str) -> str:
    return _service_family(container_name)


def _patch_platform_kafka_env(container: dict) -> None:
    ip = os.environ["ECS_HOST_PRIVATE_IP"]
    for e in container.get("environment") or []:
        if e.get("name") == "KAFKA_ADVERTISED_LISTENERS":
            e["value"] = f"PLAINTEXT://{ip}:9092"


def _add_host_ports(container: dict) -> None:
    name = container.get("name")
    if name not in HOST_PORTS:
        return
    container["portMappings"] = [
        {"containerPort": c, "hostPort": h, "protocol": "tcp"} for h, c in HOST_PORTS[name]
    ]


def _rewrite_app_env(container: dict) -> None:
    ip = os.environ["ECS_HOST_PRIVATE_IP"]
    pub = os.environ["APP_HOST"]
    for e in container.get("environment") or []:
        n = e.get("name")
        v = e.get("value", "")
        if n == "MYSQL_HOST":
            e["value"] = ip
        elif n == "MONGO_URL":
            e["value"] = f"mongodb://{ip}:27017"
        elif n == "REDIS_URL":
            e["value"] = f"redis://{ip}:6379/0"
        elif n == "KAFKA_BOOTSTRAP_SERVERS":
            e["value"] = f"{ip}:9092"
        elif n == "MINIO_ENDPOINT":
            e["value"] = f"{ip}:9000"
        elif n == "MINIO_PUBLIC_ENDPOINT":
            e["value"] = f"{pub}:9000"
        elif n == "OWNER1_JWKS_URL":
            e["value"] = f"http://{ip}:8001/.well-known/jwks.json"
        elif n == "MEMBER_PUBLIC_URL":
            e["value"] = f"http://{pub}:8002"
        elif n == "MESSAGING_SERVICE_URL":
            e["value"] = f"http://{ip}:8006"
        elif n == "PUBLIC_BASE_URL":
            e["value"] = f"http://{pub}"


def _strip_cross_task_fields(container: dict) -> None:
    container.pop("links", None)
    container.pop("dependsOn", None)


def _single_taskdef(
    family: str,
    containers: list[dict],
    volumes: list[dict] | None,
) -> dict:
    return {
        "family": family,
        "networkMode": "bridge",
        "requiresCompatibilities": ["EC2"],
        "executionRoleArn": f"arn:aws:iam::{os.environ['AWS_ACCOUNT_ID']}:role/ecsTaskExecutionRole",
        "taskRoleArn": f"arn:aws:iam::{os.environ['AWS_ACCOUNT_ID']}:role/linkedinSimTaskRole",
        "volumes": volumes or [],
        "containerDefinitions": containers,
    }


def main() -> int:
    missing = [k for k in REQUIRED_COMMON if not (os.environ.get(k) or "").strip()]
    missing.extend(_validate_backend_images())
    if missing:
        print(f"Missing required env: {', '.join(missing)}", file=sys.stderr)
        return 1
    os.environ.setdefault("OPENROUTER_API_KEY", "")

    raw = json.loads(SRC.read_text(encoding="utf-8"))
    raw = _replace_placeholders(raw)

    containers_in = raw.get("containerDefinitions") or []
    by_name = {c["name"]: copy.deepcopy(c) for c in containers_in}

    for name in PLATFORM:
        if name not in by_name:
            print(f"Missing platform container {name} in template", file=sys.stderr)
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []

    # --- Platform task ---
    plat_containers = []
    for name in ("mysql", "mongo", "redis", "kafka", "minio"):
        c = by_name[name]
        _strip_cross_task_fields(c)
        _add_host_ports(c)
        if name == "kafka":
            _patch_platform_kafka_env(c)
        plat_containers.append(c)

    plat_td = _single_taskdef("linkedin-sim-platform", plat_containers, raw.get("volumes") or [])
    plat_path = OUT_DIR / "taskdef-platform.json"
    plat_path.write_text(json.dumps(plat_td, indent=2) + "\n", encoding="utf-8")
    manifest.append(
        {
            "serviceName": "linkedin-sim-platform",
            "taskFile": str(plat_path.relative_to(ROOT)),
            "pathFilters": ["infra/mysql", "infra/mongo", "infra/ecs-ec2/ecs-taskdef.template.json", "infra/ecs-ec2/render_taskdefs.py"],
        }
    )

    # --- App + frontend tasks ---
    for c in containers_in:
        name = c.get("name")
        if name in PLATFORM or not name:
            continue
        c2 = copy.deepcopy(c)
        _strip_cross_task_fields(c2)
        _rewrite_app_env(c2)
        c2["image"] = _backend_image_for(name)
        fam = _service_family(name)
        td = _single_taskdef(fam, [c2], [])
        out_path = OUT_DIR / f"taskdef-{name}.json"
        out_path.write_text(json.dumps(td, indent=2) + "\n", encoding="utf-8")

        if name == "frontend":
            paths = ["frontend/**"]
        else:
            paths = [
                f"backend/services/{name}/**",
                "backend/services/shared/**",
                "backend/requirements.txt",
                "backend/Dockerfile",
            ]
        manifest.append(
            {
                "serviceName": _service_name(name),
                "taskFile": str(out_path.relative_to(ROOT)),
                "pathFilters": paths,
            }
        )

    man_path = OUT_DIR / "services.manifest.json"
    man_path.write_text(json.dumps({"services": manifest}, indent=2) + "\n", encoding="utf-8")
    print(str(man_path.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
