from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.environ.get('RUN_KAFKA_INTEGRATION') != '1', reason='Set RUN_KAFKA_INTEGRATION=1 to run live Kafka integration test.')
def test_live_kafka_roundtrip():
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.setdefault('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    env.setdefault('KAFKA_TEST_TOPIC', 'kafka.test.pytest')
    proc = subprocess.run(
        [sys.executable, str(repo_root / 'scripts' / 'test_kafka_roundtrip.py')],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout.strip())
    assert payload['status'] == 'ok'
    assert payload['event_type'] == 'application.submitted'
