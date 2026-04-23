"""
Mock event producer — simulates events from ALL other owners.
Run this to populate your analytics pipeline locally.

Usage:
    python scripts/seed_events.py              # default 500 events
    python scripts/seed_events.py --count 2000 # custom count
    python scripts/seed_events.py --mode kafka  # push to Kafka instead of HTTP
"""
import argparse
import asyncio
import json
import random
import uuid
import httpx
from datetime import datetime, timedelta

API_BASE = "http://localhost:8000"

# ── Fake data pools ───────────────────────────────────────────────
MEMBERS = [f"mem_{i}" for i in range(100, 600)]
RECRUITERS = [f"rec_{i}" for i in range(100, 200)]
JOBS = [f"job_{i}" for i in range(3000, 3500)]
LOCATIONS = [
    "San Jose, CA", "New York, NY", "Austin, TX", "Seattle, WA",
    "Chicago, IL", "Denver, CO", "Boston, MA", "Miami, FL",
    "Portland, OR", "San Francisco, CA", "Atlanta, GA", "Dallas, TX",
]
SKILLS = ["Python", "Java", "Kafka", "MySQL", "MongoDB", "Redis", "FastAPI", "React", "AWS", "Docker"]


def _trace():
    return f"trc_{uuid.uuid4().hex[:8]}"


def _idem():
    return f"idem_{uuid.uuid4().hex[:12]}"


def _rand_time(days_back=30):
    return (datetime.utcnow() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )).isoformat()


# ── Event generators (one per owner) ──────────────────────────────

def gen_owner1_events(n):
    """Auth events: user.created, user.logout"""
    events = []
    for _ in range(n):
        etype = random.choice(["user.created", "user.logout"])
        user_id = random.choice(MEMBERS + RECRUITERS)
        events.append({
            "event_type": etype,
            "actor_id": user_id,
            "entity": {"entity_type": "user", "entity_id": user_id},
            "trace_id": _trace(),
            "payload": {"user_type": "member" if user_id.startswith("mem") else "recruiter"},
            "idempotency_key": _idem(),
        })
    return events


def gen_owner2_events(n):
    """Member events: member.created, member.updated, profile.viewed"""
    events = []
    for _ in range(n):
        etype = random.choice(["member.created", "member.updated", "profile.viewed"])
        member = random.choice(MEMBERS)
        viewer = random.choice(MEMBERS) if etype == "profile.viewed" else member
        events.append({
            "event_type": etype,
            "actor_id": viewer,
            "entity": {"entity_type": "member", "entity_id": member},
            "trace_id": _trace(),
            "payload": {
                "skills": random.sample(SKILLS, k=random.randint(1, 4)),
                "location": random.choice(LOCATIONS),
            },
            "idempotency_key": _idem(),
        })
    return events


def gen_owner3_events(n):
    """Recruiter events: recruiter.created, recruiter.updated"""
    events = []
    for _ in range(n):
        rec = random.choice(RECRUITERS)
        events.append({
            "event_type": random.choice(["recruiter.created", "recruiter.updated"]),
            "actor_id": rec,
            "entity": {"entity_type": "recruiter", "entity_id": rec},
            "trace_id": _trace(),
            "payload": {"company": f"Company_{random.randint(1,50)}"},
            "idempotency_key": _idem(),
        })
    return events


def gen_owner4_events(n):
    """Job events: job.created, job.viewed, job.updated, job.closed, job.search.executed"""
    events = []
    for _ in range(n):
        etype = random.choices(
            ["job.viewed", "job.search.executed", "job.created", "job.updated", "job.closed"],
            weights=[40, 25, 15, 10, 10],
        )[0]
        job = random.choice(JOBS)
        actor = random.choice(MEMBERS) if etype in ("job.viewed", "job.search.executed") else random.choice(RECRUITERS)
        events.append({
            "event_type": etype,
            "actor_id": actor,
            "entity": {"entity_type": "job", "entity_id": job},
            "trace_id": _trace(),
            "payload": {
                "location": random.choice(LOCATIONS),
                "skills_required": random.sample(SKILLS, k=random.randint(1, 3)),
            },
            "idempotency_key": _idem(),
        })
    return events


def gen_owner5_events(n):
    """Application events: application.submitted, application.status.updated"""
    events = []
    for _ in range(n):
        etype = random.choices(
            ["application.submitted", "application.status.updated", "application.note.added"],
            weights=[50, 35, 15],
        )[0]
        member = random.choice(MEMBERS)
        job = random.choice(JOBS)
        app_id = f"app_{random.randint(8000,9999)}"
        payload = {"job_id": job, "member_id": member}
        if etype == "application.status.updated":
            payload["new_status"] = random.choice(["reviewed", "shortlisted", "rejected", "interview", "offered"])
        events.append({
            "event_type": etype,
            "actor_id": member if etype == "application.submitted" else random.choice(RECRUITERS),
            "entity": {"entity_type": "application", "entity_id": app_id},
            "trace_id": _trace(),
            "payload": payload,
            "idempotency_key": _idem(),
        })
    return events


def gen_owner6_events(n):
    """Social events: message.sent, connection.requested, connection.accepted"""
    events = []
    for _ in range(n):
        etype = random.choices(
            ["message.sent", "connection.requested", "connection.accepted"],
            weights=[50, 25, 25],
        )[0]
        sender = random.choice(MEMBERS)
        receiver = random.choice([m for m in MEMBERS if m != sender])
        events.append({
            "event_type": etype,
            "actor_id": sender,
            "entity": {
                "entity_type": "thread" if etype == "message.sent" else "connection",
                "entity_id": f"thr_{random.randint(1,999)}" if etype == "message.sent" else f"conn_{random.randint(1,999)}",
            },
            "trace_id": _trace(),
            "payload": {"receiver_id": receiver, "location": random.choice(LOCATIONS)},
            "idempotency_key": _idem(),
        })
    return events


def gen_owner8_events(n):
    """AI events: ai.requested, ai.completed, ai.approved, ai.rejected"""
    events = []
    for _ in range(n):
        etype = random.choices(
            ["ai.requested", "ai.completed", "ai.approved", "ai.rejected"],
            weights=[35, 30, 25, 10],
        )[0]
        rec = random.choice(RECRUITERS)
        task_id = f"ait_{random.randint(3000,4000)}"
        events.append({
            "event_type": etype,
            "actor_id": rec,
            "entity": {"entity_type": "ai_task", "entity_id": task_id},
            "trace_id": _trace(),
            "payload": {"job_id": random.choice(JOBS), "task_type": "shortlist_and_outreach"},
            "idempotency_key": _idem(),
        })
    return events


# ── Main ──────────────────────────────────────────────────────────

async def seed_via_http(count: int):
    """Send mock events through the /events/ingest HTTP endpoint."""
    # Distribute events across owners roughly proportional to real traffic
    generators = [
        (gen_owner1_events, 0.08),
        (gen_owner2_events, 0.12),
        (gen_owner3_events, 0.05),
        (gen_owner4_events, 0.30),
        (gen_owner5_events, 0.20),
        (gen_owner6_events, 0.15),
        (gen_owner8_events, 0.10),
    ]

    all_events = []
    for gen_fn, weight in generators:
        n = max(1, int(count * weight))
        all_events.extend(gen_fn(n))

    random.shuffle(all_events)
    all_events = all_events[:count]

    print(f"Sending {len(all_events)} events to {API_BASE}/events/ingest ...")
    success = 0
    errors = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, event in enumerate(all_events):
            try:
                resp = await client.post(f"{API_BASE}/events/ingest", json=event)
                if resp.status_code == 200:
                    success += 1
                else:
                    errors += 1
                    if errors <= 5:
                        print(f"  Error [{resp.status_code}]: {resp.text[:120]}")
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Connection error: {e}")

            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{len(all_events)} (ok={success}, err={errors})")

    print(f"\nDone! {success} succeeded, {errors} failed out of {len(all_events)} total.")


async def seed_via_kafka(count: int):
    """Push mock events directly to Kafka topics (bypasses HTTP API)."""
    from aiokafka import AIOKafkaProducer

    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:19092",
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
    )
    await producer.start()

    generators = [
        (gen_owner1_events, 0.08),
        (gen_owner2_events, 0.12),
        (gen_owner3_events, 0.05),
        (gen_owner4_events, 0.30),
        (gen_owner5_events, 0.20),
        (gen_owner6_events, 0.15),
        (gen_owner8_events, 0.10),
    ]

    all_events = []
    for gen_fn, weight in generators:
        n = max(1, int(count * weight))
        all_events.extend(gen_fn(n))

    random.shuffle(all_events)
    all_events = all_events[:count]

    print(f"Publishing {len(all_events)} events directly to Kafka ...")
    for i, event in enumerate(all_events):
        event["timestamp"] = datetime.utcnow().isoformat()
        await producer.send_and_wait(event["event_type"], event)
        if (i + 1) % 100 == 0:
            print(f"  Published {i+1}/{len(all_events)}")

    await producer.stop()
    print(f"Done! {len(all_events)} events published to Kafka.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed mock events for Owner 7 Analytics")
    parser.add_argument("--count", type=int, default=500, help="Number of events to generate")
    parser.add_argument("--mode", choices=["http", "kafka"], default="http", help="Delivery mode")
    args = parser.parse_args()

    asyncio.run(
        seed_via_http(args.count) if args.mode == "http" else seed_via_kafka(args.count)
    )
