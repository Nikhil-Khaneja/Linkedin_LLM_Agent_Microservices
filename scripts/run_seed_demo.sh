#!/usr/bin/env bash
# Host-side seed script needs `requests`; backend deps live in Docker only.
# Use a small repo-local venv so system Python does not need global installs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv-bootstrap"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating $VENV (requests for scripts/seed_demo_data.py)"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r "$ROOT/scripts/requirements_bootstrap_host.txt"
fi
exec "$VENV/bin/python" "$ROOT/scripts/seed_demo_data.py" "$@"
