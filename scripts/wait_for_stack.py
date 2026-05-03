#!/usr/bin/env python3
from __future__ import annotations
import os
import subprocess
import sys
import time

SERVICES = sys.argv[1:]
# First `npm install` + CRA boot often exceeds 300s on a cold machine. Override with WAIT_FOR_STACK_TIMEOUT.
_default = 900 if "frontend" in SERVICES else 300
TIMEOUT = int(os.environ.get("WAIT_FOR_STACK_TIMEOUT", str(_default)))

if not SERVICES:
    print("Usage: wait_for_stack.py <service> [<service> ...]", file=sys.stderr)
    sys.exit(2)


def run(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def service_status(service: str) -> str:
    cid = run("docker", "compose", "ps", "-q", service)
    if not cid:
        cid = run("docker", "compose", "ps", "-a", "-q", service)
        if cid:
            status = run("docker", "inspect", "--format", "{{.State.Status}}", cid)
            return status or "stopped"
        return "missing"
    status = run("docker", "inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", cid)
    return status or "unknown"


deadline = time.time() + TIMEOUT
pending = set(SERVICES)
while pending and time.time() < deadline:
    done = []
    for svc in list(pending):
        status = service_status(svc)
        print(f"[{svc}] {status}")
        if status in {"healthy", "running"}:
            done.append(svc)
    for svc in done:
        pending.discard(svc)
    if pending:
        time.sleep(5)

if pending:
    print(f"Timed out waiting for: {', '.join(sorted(pending))}", file=sys.stderr)
    sys.exit(1)

print("All requested services are ready.")
