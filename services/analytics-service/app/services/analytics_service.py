"""
Core analytics business logic:
  - event ingest + Kafka re-publish
  - dashboard rollup queries
  - benchmark storage
"""
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.utils.db import get_db, get_redis
from app.config.settings import get_settings
from app.models.events import (
    EventIngestRequest, EventIngestResponse,
    TopJobsRequest, FunnelRequest, FunnelResponse,
    GeoRequest, MemberDashboardRequest, MemberDashboardResponse,
    BenchmarkReportRequest, BenchmarkReportResponse,
)

logger = logging.getLogger(__name__)


# ── Kafka producer (lazy init) ────────────────────────────────────
_producer = None


async def get_producer():
    global _producer
    if _producer is None:
        from aiokafka import AIOKafkaProducer
        settings = get_settings()
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )
        await _producer.start()
    return _producer


async def stop_producer():
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


# ── Event Ingest ──────────────────────────────────────────────────

async def ingest_event(req: EventIngestRequest) -> EventIngestResponse:
    db = get_db()
    event_id = f"evt_{uuid.uuid4().hex[:8]}"
    trace_id = req.trace_id or f"trc_{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow()

    # Idempotency check — return 409 so callers know this was a duplicate
    if req.idempotency_key:
        existing = await db.events_raw.find_one({"idempotency_key": req.idempotency_key})
        if existing:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "duplicate_event",
                    "message": "Event with this idempotency_key already processed",
                    "original_event_id": existing["event_id"],
                }
            )

    # Store raw event
    doc = {
        "event_id": event_id,
        "event_type": req.event_type,
        "trace_id": trace_id,
        "timestamp": now,
        "actor_id": req.actor_id,
        "entity": req.entity.model_dump(),
        "payload": req.payload,
        "idempotency_key": req.idempotency_key,
    }
    await db.events_raw.insert_one(doc)

    # Re-publish normalized event to Kafka
    try:
        producer = await get_producer()
        kafka_msg = {
            "event_type": req.event_type,
            "trace_id": trace_id,
            "timestamp": now.isoformat(),
            "actor_id": req.actor_id,
            "entity": req.entity.model_dump(),
            "payload": req.payload,
            "idempotency_key": req.idempotency_key,
        }
        await producer.send_and_wait(f"analytics.{req.event_type}", kafka_msg)
    except Exception as e:
        logger.warning(f"Kafka publish failed (non-blocking): {e}")

    # Update rollups inline (lightweight increment)
    await _update_rollups(req, now)

    return EventIngestResponse(accepted=True, event_id=event_id)


async def _update_rollups(req: EventIngestRequest, now: datetime):
    """Increment rollup counters based on event type."""
    db = get_db()
    date_key = now.strftime("%Y-%m-%d")

    if req.event_type in ("job.viewed", "job.search.executed", "job.created", "job.closed"):
        job_id = req.entity.entity_id if req.entity.entity_type == "job" else req.payload.get("job_id")
        if job_id:
            await db.recruiter_dash_rollups.update_one(
                {"job_id": job_id, "date": date_key},
                {"$inc": {req.event_type.replace(".", "_"): 1}},
                upsert=True,
            )

    if req.event_type == "application.submitted":
        job_id = req.payload.get("job_id")
        member_id = req.payload.get("member_id") or req.actor_id
        if job_id:
            await db.recruiter_dash_rollups.update_one(
                {"job_id": job_id, "date": date_key},
                {"$inc": {"application_submitted": 1}},
                upsert=True,
            )
        if member_id:
            await db.member_dash_rollups.update_one(
                {"member_id": member_id, "date": date_key},
                {"$inc": {"applications_sent": 1}},
                upsert=True,
            )

    if req.event_type == "application.status.updated":
        member_id = req.payload.get("member_id") or req.actor_id
        if member_id:
            new_status = req.payload.get("new_status", "unknown")
            await db.member_dash_rollups.update_one(
                {"member_id": member_id, "date": date_key},
                {"$inc": {f"status_{new_status}": 1}},
                upsert=True,
            )

    if req.event_type in ("message.sent",):
        receiver = req.payload.get("receiver_id")
        if receiver:
            await db.member_dash_rollups.update_one(
                {"member_id": receiver, "date": date_key},
                {"$inc": {"messages_received": 1}},
                upsert=True,
            )

    if req.event_type in ("connection.accepted",):
        for mid in [req.actor_id, req.payload.get("receiver_id")]:
            if mid:
                await db.member_dash_rollups.update_one(
                    {"member_id": mid, "date": date_key},
                    {"$inc": {"connections": 1}},
                    upsert=True,
                )

    if req.event_type == "profile.viewed":
        viewed_id = req.entity.entity_id
        if viewed_id:
            await db.member_dash_rollups.update_one(
                {"member_id": viewed_id, "date": date_key},
                {"$inc": {"profile_views": 1}},
                upsert=True,
            )


# ── Top Jobs ──────────────────────────────────────────────────────

async def get_top_jobs(req: TopJobsRequest) -> list:
    db = get_db()
    redis = get_redis()
    settings = get_settings()

    cache_key = f"analytics:top_jobs:{req.metric}:{req.limit}:{req.days}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    since = datetime.utcnow() - timedelta(days=req.days)
    metric_field = {
        "applications": "application_submitted",
        "views": "job_viewed",
        "saves": "job_saved",
    }.get(req.metric, "application_submitted")

    pipeline = [
        {"$match": {"date": {"$gte": since.strftime("%Y-%m-%d")}}},
        {"$group": {"_id": "$job_id", "total": {"$sum": f"${metric_field}"}}},
        {"$sort": {"total": -1}},
        {"$limit": req.limit},
    ]
    results = []
    async for doc in db.recruiter_dash_rollups.aggregate(pipeline):
        results.append({"job_id": doc["_id"], "count": doc["total"]})

    await redis.setex(cache_key, settings.REDIS_CACHE_TTL, json.dumps(results))
    return results


# ── Funnel ────────────────────────────────────────────────────────

async def get_funnel(req: FunnelRequest) -> FunnelResponse:
    db = get_db()
    redis = get_redis()
    settings = get_settings()

    cache_key = f"analytics:funnel:{req.job_id or 'all'}:{req.days}"
    cached = await redis.get(cache_key)
    if cached:
        return FunnelResponse(**json.loads(cached))

    since = datetime.utcnow() - timedelta(days=req.days)
    match_filter = {"timestamp": {"$gte": since}}
    if req.job_id:
        match_filter["entity.entity_id"] = req.job_id

    views = await db.events_raw.count_documents({**match_filter, "event_type": "job.viewed"})
    saves = await db.events_raw.count_documents({**match_filter, "event_type": "job.saved"})
    applications = await db.events_raw.count_documents({**match_filter, "event_type": "application.submitted"})

    result = FunnelResponse(
        views=views,
        saves=saves,
        applications=applications,
        view_to_save_rate=round(saves / views, 4) if views else 0,
        save_to_apply_rate=round(applications / saves, 4) if saves else 0,
        view_to_apply_rate=round(applications / views, 4) if views else 0,
    )

    await redis.setex(cache_key, settings.REDIS_CACHE_TTL, result.model_dump_json())
    return result


# ── Geo Distribution ──────────────────────────────────────────────

async def get_geo(req: GeoRequest) -> list:
    db = get_db()
    redis = get_redis()
    settings = get_settings()

    cache_key = f"analytics:geo:{req.job_id or 'all'}:{req.event_type or 'all'}:{req.city or ''}:{req.state or ''}:{req.days}:{req.limit}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    since = datetime.utcnow() - timedelta(days=req.days)

    # Build event_type filter
    if req.event_type:
        event_types = [req.event_type]
    else:
        event_types = ["job.viewed", "application.submitted"]

    match_filter = {
        "timestamp": {"$gte": since},
        "event_type": {"$in": event_types},
    }

    if req.job_id:
        match_filter["entity.entity_id"] = req.job_id

    # City/state filter — location stored as "City, ST" e.g. "San Jose, CA"
    if req.city and req.state:
        match_filter["payload.location"] = {"$regex": f"^{req.city}.*{req.state}$", "$options": "i"}
    elif req.city:
        match_filter["payload.location"] = {"$regex": req.city, "$options": "i"}
    elif req.state:
        match_filter["payload.location"] = {"$regex": f",\\s*{req.state}$", "$options": "i"}

    pipeline = [
        {"$match": match_filter},
        {"$group": {
            "_id": "$payload.location",
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
        {"$limit": req.limit},
    ]

    results = []
    async for doc in db.events_raw.aggregate(pipeline):
        results.append({"location": doc["_id"], "count": doc["count"]})

    await redis.setex(cache_key, settings.REDIS_CACHE_TTL, json.dumps(results))
    return results


# ── Member Dashboard ──────────────────────────────────────────────

async def get_member_dashboard(req: MemberDashboardRequest) -> MemberDashboardResponse:
    db = get_db()

    pipeline = [
        {"$match": {"member_id": req.member_id}},
        {"$group": {
            "_id": None,
            "profile_views": {"$sum": {"$ifNull": ["$profile_views", 0]}},
            "applications_sent": {"$sum": {"$ifNull": ["$applications_sent", 0]}},
            "connections": {"$sum": {"$ifNull": ["$connections", 0]}},
            "messages_received": {"$sum": {"$ifNull": ["$messages_received", 0]}},
        }},
    ]

    result = None
    async for doc in db.member_dash_rollups.aggregate(pipeline):
        result = doc

    if not result:
        return MemberDashboardResponse(
            profile_views=0, applications_sent=0,
            connections=0, messages_received=0, job_matches=0,
        )

    return MemberDashboardResponse(
        profile_views=result.get("profile_views", 0),
        applications_sent=result.get("applications_sent", 0),
        connections=result.get("connections", 0),
        messages_received=result.get("messages_received", 0),
        job_matches=0,  # populated by AI service later
    )


# ── Benchmark Report ──────────────────────────────────────────────

async def store_benchmark(req: BenchmarkReportRequest) -> BenchmarkReportResponse:
    db = get_db()
    benchmark_id = f"bench_{uuid.uuid4().hex[:8]}"

    doc = {
        "benchmark_id": benchmark_id,
        "scenario": req.scenario,
        "owner_id": req.owner_id,
        "service_name": req.service_name,
        "results": req.results,
        "metadata": req.metadata,
        "created_at": datetime.utcnow(),
    }
    await db.benchmark_runs.insert_one(doc)

    # Publish benchmark.completed to Kafka
    try:
        producer = await get_producer()
        await producer.send_and_wait("benchmark.completed", {
            "event_type": "benchmark.completed",
            "benchmark_id": benchmark_id,
            "scenario": req.scenario,
            "owner_id": req.owner_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.warning(f"Kafka publish for benchmark failed: {e}")

    return BenchmarkReportResponse(benchmark_id=benchmark_id, status="stored")
