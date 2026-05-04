#!/usr/bin/env python3
"""
Insert demo documents into MongoDB `linkedin_sim.notifications` (same collection the member API reads).

Use after port-forwarding Mongo from AWS (see infra/ecs-ec2/README.md "Loading data on AWS").

  export MONGO_URI=mongodb://127.0.0.1:27018
  export MONGO_DATABASE=linkedin_sim
  python3 scripts/mongo_seed_demo.py --member-id mem_501 --count 10
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

try:
    from pymongo import MongoClient
except ImportError as e:
    print("pip install pymongo", file=sys.stderr)
    raise SystemExit(1) from e


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--member-id", required=True, help="Target member_id (e.g. mem_501)")
    p.add_argument("--count", type=int, default=5)
    args = p.parse_args()

    uri = os.environ.get("MONGO_URI") or os.environ.get("MONGO_URL") or "mongodb://127.0.0.1:27017"
    dbn = os.environ.get("MONGO_DATABASE", "linkedin_sim")
    n = max(1, min(int(args.count), 500))

    client = MongoClient(uri)
    col = client[dbn]["notifications"]
    now = datetime.now(timezone.utc).isoformat()
    docs = [
        {
            "_id": f"ntf_seed_{uuid4().hex[:10]}",
            "member_id": args.member_id,
            "type": "profile.viewed",
            "title": "Profile viewed",
            "body": f"Demo notification {i + 1} for load testing.",
            "actor_id": "mem_demo",
            "actor_name": "Demo viewer",
            "target_url": "/profile/mem_demo",
            "data": {"seed": True, "i": i},
            "is_read": i % 3 == 0,
            "created_at": now,
        }
        for i in range(n)
    ]
    col.insert_many(docs)
    print(f"Inserted {len(docs)} docs into {dbn}.notifications for member_id={args.member_id}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
