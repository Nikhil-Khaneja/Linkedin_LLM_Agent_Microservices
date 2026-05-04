#!/usr/bin/env python3
"""
Seed a synthetic member connection graph in MongoDB (same DB/collections as messaging_connections_service).

Connections live in MONGO_DATABASE (default linkedin_sim_docs): collection "connections".
Optionally sync MySQL members.connections_count for bulk-seeded members.

Usage (after SSH tunnels: Mongo e.g. -L 27018:127.0.0.1:27017, MySQL e.g. -L 3307:127.0.0.1:3306):

  export MONGO_URI=mongodb://127.0.0.1:27018
  export MONGO_DATABASE=linkedin_sim_docs
  export MYSQL_HOST=127.0.0.1 MYSQL_PORT=3307 MYSQL_USER=root MYSQL_PASSWORD=root MYSQL_DATABASE=linkedin_sim

  python3 scripts/mongo_seed_member_network.py --run-id aws1 --degree 5 --replace

  --degree N: each member links to the next N members in sorted id order (mod count), undirected unique pairs.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone


def _run_token(s: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", (s or "seed").lower())[:24]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    p = argparse.ArgumentParser(description="Seed MongoDB connections + optional MySQL counts for bulk members.")
    p.add_argument("--run-id", default="aws1", help="Must match bulk_seed members (mem_{run}_*)")
    p.add_argument("--degree", type=int, default=5, help="Each member connects to next K others in sorted id ring")
    p.add_argument("--replace", action="store_true", help="Remove prior bulk_net_{run}_* connection docs")
    p.add_argument("--skip-mysql", action="store_true", help="Do not update members.connections_count")
    args = p.parse_args()

    run = _run_token(args.run_id)
    deg = max(1, int(args.degree))

    try:
        from pymongo import MongoClient
    except ImportError:
        print("pip install pymongo", file=sys.stderr)
        return 1

    mongo_uri = os.environ.get("MONGO_URI") or os.environ.get("MONGO_URL") or "mongodb://127.0.0.1:27017"
    mongo_db = os.environ.get("MONGO_DATABASE", "linkedin_sim_docs")

    prefix = f"mem_{run}_"
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=8000)
    try:
        db = client[mongo_db]
        coll = db["connections"]

        members: list[str] = []
        try:
            import pymysql

            conn = pymysql.connect(
                host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
                port=int(os.environ.get("MYSQL_PORT", "3306")),
                user=os.environ.get("MYSQL_USER", "root"),
                password=os.environ.get("MYSQL_PASSWORD", "root"),
                database=os.environ.get("MYSQL_DATABASE", "linkedin_sim"),
                charset="utf8mb4",
            )
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT member_id FROM members WHERE member_id LIKE %s ORDER BY member_id",
                    (f"{prefix}%",),
                )
                members = [r[0] for r in cur.fetchall()]
            conn.close()
        except Exception as e:
            print(f"MySQL member list failed ({e}); using mem_{run}_0000001..1000", file=sys.stderr)
            members = [f"mem_{run}_{i:07d}" for i in range(1, 1001)]

        if len(members) < 2:
            print(f"Need at least 2 members matching {prefix}*. Found {len(members)}.", file=sys.stderr)
            return 1

        if args.replace:
            coll.delete_many({"source_request_id": {"$regex": f"^bulk_net_{re.escape(run)}_"}})

        pairs: set[tuple[str, str]] = set()
        n = len(members)
        for i, a in enumerate(members):
            for k in range(1, deg + 1):
                b = members[(i + k) % n]
                if a == b:
                    continue
                lo, hi = (a, b) if a < b else (b, a)
                pairs.add((lo, hi))

        docs: list[dict] = []
        for lo, hi in sorted(pairs):
            cid = f"cnn_{uuid.uuid4().hex[:10]}"
            docs.append(
                {
                    "connection_id": cid,
                    "pair_key": "|".join(sorted([lo, hi])),
                    "user_a": lo,
                    "user_b": hi,
                    "source_request_id": f"bulk_net_{run}_{cid}",
                    "connected_at": _now_iso(),
                }
            )

        batch = 500
        for i in range(0, len(docs), batch):
            coll.insert_many(docs[i : i + batch])

        print(f"MongoDB {mongo_db}.connections inserted={len(docs)} edges for {len(members)} members (run={run}, degree={deg})")

        if not args.skip_mysql:
            try:
                import pymysql

                conn = pymysql.connect(
                    host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
                    port=int(os.environ.get("MYSQL_PORT", "3306")),
                    user=os.environ.get("MYSQL_USER", "root"),
                    password=os.environ.get("MYSQL_PASSWORD", "root"),
                    database=os.environ.get("MYSQL_DATABASE", "linkedin_sim"),
                    charset="utf8mb4",
                )
                counts: defaultdict[str, int] = defaultdict(int)
                for lo, hi in pairs:
                    counts[lo] += 1
                    counts[hi] += 1
                with conn.cursor() as cur:
                    for mid, c in counts.items():
                        cur.execute(
                            "UPDATE members SET connections_count = %s WHERE member_id = %s",
                            (c, mid),
                        )
                conn.commit()
                conn.close()
                print(f"MySQL members.connections_count updated for {len(counts)} members.")
            except Exception as e:
                print(f"MySQL count sync skipped: {e}", file=sys.stderr)
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
