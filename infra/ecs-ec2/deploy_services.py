#!/usr/bin/env python3
"""Register task definitions and create/update ECS EC2 (bridge) services from services.manifest.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Data-plane ECS service (MySQL, Mongo, Redis, Kafka, MinIO). Rolled only when explicitly
# selected, when DEPLOY_SELECTION=ALL_WITH_PLATFORM, or when missing / not active (bootstrap).
PLATFORM_SERVICE = "linkedin-sim-platform"


def run(*args: str) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        raise SystemExit(r.returncode)
    return (r.stdout or "").strip()


def _platform_needs_deploy(region: str, cluster: str) -> bool:
    """True if platform service is missing, inactive, or scaled to zero (apps need it up)."""
    n = run(
        "aws",
        "ecs",
        "describe-services",
        "--cluster",
        cluster,
        "--services",
        PLATFORM_SERVICE,
        "--region",
        region,
        "--query",
        "length(services)",
        "--output",
        "text",
    )
    if n == "0" or n == "None":
        return True
    st = run(
        "aws",
        "ecs",
        "describe-services",
        "--cluster",
        cluster,
        "--services",
        PLATFORM_SERVICE,
        "--region",
        region,
        "--query",
        "services[0].status",
        "--output",
        "text",
    )
    if st in ("INACTIVE", "DRAINING", "None", ""):
        return True
    dc = run(
        "aws",
        "ecs",
        "describe-services",
        "--cluster",
        cluster,
        "--services",
        PLATFORM_SERVICE,
        "--region",
        region,
        "--query",
        "services[0].desiredCount",
        "--output",
        "text",
    )
    try:
        if int(dc or "0") < 1:
            return True
    except ValueError:
        return True
    return False


def main() -> int:
    root = Path(os.environ.get("GITHUB_WORKSPACE") or os.environ.get("ROOT") or ".").resolve()
    region = os.environ["AWS_REGION"]
    cluster = os.environ["ECS_CLUSTER"]
    selection = (os.environ.get("DEPLOY_SELECTION") or "ALL_APPS").strip()
    sel_u = selection.upper()
    manifest_path = root / "infra" / "ecs-ec2" / "rendered" / "services.manifest.json"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    services = data.get("services") or []
    names_in_manifest = [s["serviceName"] for s in services]
    want_raw = {s.strip() for s in selection.split(",") if s.strip()}

    # ALL_WITH_PLATFORM: every service including data plane.
    all_with_platform = sel_u == "ALL_WITH_PLATFORM" or "ALL_WITH_PLATFORM" in want_raw

    # ALL_APPS / ALL / empty: all application services + frontend; never data plane unless added below.
    # Legacy "ALL" from older CI means apps-only (do not bounce MySQL/Mongo/Kafka on routine deploys).
    all_apps_only = (
        sel_u in ("ALL_APPS", "ALL", "")
        or "ALL_APPS" in want_raw
        or ("ALL" in want_raw and not all_with_platform)
        or (not want_raw and not all_with_platform)
    )

    want: set[str] = set()
    if all_with_platform:
        want = set(names_in_manifest)
    elif all_apps_only:
        want = {n for n in names_in_manifest if n != PLATFORM_SERVICE}
    else:
        want = {w for w in want_raw if w not in ("ALL_APPS", "ALL", "ALL_WITH_PLATFORM")}

    if not want:
        print("No services selected for deploy.", file=sys.stderr)
        return 1

    to_run: list[tuple[str, Path]] = []
    for s in services:
        name = s["serviceName"]
        rel = s["taskFile"]
        if name in want:
            to_run.append((name, root / rel))

    def _order(item: tuple[str, Path]) -> tuple[int, str]:
        n = item[0]
        if n == "linkedin-sim-platform":
            return (0, n)
        if n == "linkedin-sim-frontend":
            return (2, n)
        return (1, n)

    to_run.sort(key=_order)

    run_names = {x[0] for x in to_run}
    if PLATFORM_SERVICE not in run_names and _platform_needs_deploy(region, cluster):
        plat = next((s for s in services if s.get("serviceName") == PLATFORM_SERVICE), None)
        if not plat:
            print(f"Manifest missing {PLATFORM_SERVICE}; cannot bootstrap data plane.", file=sys.stderr)
            return 1
        td = root / plat["taskFile"]
        to_run.insert(0, (PLATFORM_SERVICE, td))
        print(f"[deploy] {PLATFORM_SERVICE} missing or inactive; including data plane this run.")
        to_run.sort(key=_order)

    if not to_run:
        print("No services selected for deploy.", file=sys.stderr)
        return 1

    for svc_name, td_path in to_run:
        if not td_path.is_file():
            print(f"Missing task definition file: {td_path}", file=sys.stderr)
            return 1
        print(f"[deploy] register-task-definition {svc_name} <- {td_path}")
        td_arn = run(
            "aws",
            "ecs",
            "register-task-definition",
            "--cli-input-json",
            f"file://{td_path}",
            "--region",
            region,
            "--query",
            "taskDefinition.taskDefinitionArn",
            "--output",
            "text",
        )
        n = run(
            "aws",
            "ecs",
            "describe-services",
            "--cluster",
            cluster,
            "--services",
            svc_name,
            "--region",
            region,
            "--query",
            "length(services)",
            "--output",
            "text",
        )
        st = ""
        if n != "0":
            st = run(
                "aws",
                "ecs",
                "describe-services",
                "--cluster",
                cluster,
                "--services",
                svc_name,
                "--region",
                region,
                "--query",
                "services[0].status",
                "--output",
                "text",
            )
        if n == "0" or st in ("INACTIVE", "None", "DRAINING", ""):
            print(f"[deploy] create-service {svc_name}")
            run(
                "aws",
                "ecs",
                "create-service",
                "--cluster",
                cluster,
                "--service-name",
                svc_name,
                "--task-definition",
                td_arn,
                "--desired-count",
                "1",
                "--launch-type",
                "EC2",
                "--scheduling-strategy",
                "REPLICA",
                "--deployment-configuration",
                "maximumPercent=100,minimumHealthyPercent=0",
                "--region",
                region,
            )
        else:
            print(f"[deploy] update-service {svc_name}")
            run(
                "aws",
                "ecs",
                "update-service",
                "--cluster",
                cluster,
                "--service",
                svc_name,
                "--task-definition",
                td_arn,
                "--force-new-deployment",
                "--region",
                region,
            )

    names = [x[0] for x in to_run]
    print(f"[deploy] wait services-stable: {', '.join(names)}")
    run(
        "aws",
        "ecs",
        "wait",
        "services-stable",
        "--cluster",
        cluster,
        "--services",
        *names,
        "--region",
        region,
    )
    print("[deploy] stable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
