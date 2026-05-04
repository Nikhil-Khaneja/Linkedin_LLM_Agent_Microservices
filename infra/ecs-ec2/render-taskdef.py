#!/usr/bin/env python3
"""Deprecated: use `python3 infra/ecs-ec2/render_taskdefs.py` (multi-service)."""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "render-taskdef.py is deprecated. Use: python3 infra/ecs-ec2/render_taskdefs.py\n"
        "Required env: AWS_REGION AWS_ACCOUNT_ID APP_HOST ECS_HOST_PRIVATE_IP "
        "FRONTEND_IMAGE MYSQL_IMAGE MONGO_IMAGE and either BACKEND_IMAGE (single image for all apps) "
        "or BACKEND_IMAGE_AUTH_SERVICE … BACKEND_IMAGE_AI_ORCHESTRATOR_SERVICE (per-service). "
        "[OPENROUTER_API_KEY]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
