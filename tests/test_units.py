"""
Owner 7 — Unit Test Suite
Tests every module in isolation using mocks (no Docker / live services needed).

Run with:
    pip install pytest pytest-asyncio
    pytest tests/test_units.py -v
"""
import pytest
pytestmark = pytest.mark.asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1: app/config/settings.py
# What it does: loads env vars into a typed Settings object
# ─────────────────────────────────────────────────────────────────────────────

class TestSettings:
    """Settings loads defaults and can be overridden via env vars."""

    def test_defaults(self):
        from app.config.settings import Settings
        s = Settings()
        assert s.KAFKA_BOOTSTRAP_SERVERS == "localhost:19092"
        assert s.MONGODB_DB == "analytics"
        assert s.REDIS_CACHE_TTL == 300
        assert s.ENV == "development"
        assert s.SERVICE_NAME == "owner7-analytics"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("MONGODB_DB", "test_db")
        monkeypatch.setenv("REDIS_CACHE_TTL", "60")
        from app.config.settings import Settings
        s = Settings()
        assert s.MONGODB_DB == "test_db"
        assert s.REDIS_CACHE_TTL == 60


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2: app/models/events.py
# What it does: Pydantic models — validates request/response shapes
# ─────────────────────────────────────────────────────────────────────────────

class TestModels:
    """Pydantic models accept valid data and reject invalid data."""

    def test_event_ingest_request_valid(self):
        from app.models.events import EventIngestRequest, EntityRef
        req = EventIngestRequest(
            event_type="job.viewed",
            actor_id="mem_123",
            entity=EntityRef(entity_type="job", entity_id="job_999"),
            payload={"location": "San Jose, CA"},
        )
        assert req.event_type == "job.viewed"
        assert req.entity.entity_id == "job_999"
        assert req.idempotency_key is None  # optional, defaults to None

    def test_event_ingest_request_missing_required(self):
        from pydantic import ValidationError
        from app.models.events import EventIngestRequest
        with pytest.raises(ValidationError):
            EventIngestRequest(actor_id="mem_123")  # missing event_type and entity

    def test_entity_ref(self):
        from app.models.events import EntityRef
        e = EntityRef(entity_type="application", entity_id="app_001")
        assert e.entity_type == "application"

    def test_top_jobs_request_defaults(self):
        from app.models.events import TopJobsRequest
        req = TopJobsRequest()
        assert req.metric == "applications"
        assert req.limit == 10
        assert req.days == 30

    def test_funnel_response(self):
        from app.models.events import FunnelResponse
        r = FunnelResponse(
            views=100, saves=40, applications=20,
            view_to_save_rate=0.4, save_to_apply_rate=0.5, view_to_apply_rate=0.2,
        )
        assert r.view_to_apply_rate == 0.2

    def test_benchmark_request_requires_scenario(self):
        from pydantic import ValidationError
        from app.models.events import BenchmarkReportRequest
        with pytest.raises(ValidationError):
            BenchmarkReportRequest(owner_id="owner7", service_name="svc", results={})

    def test_member_dashboard_response(self):
        from app.models.events import MemberDashboardResponse
        r = MemberDashboardResponse(
            profile_views=5, applications_sent=3,
            connections=10, messages_received=7, job_matches=0,
        )
        assert r.connections == 10


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3: app/utils/db.py
# What it does: creates MongoDB + Redis singletons, exposes get_db() / get_redis()
# ─────────────────────────────────────────────────────────────────────────────

class TestDb:
    """get_db() and get_redis() return None before connect, singleton after."""

    def test_get_db_before_connect_returns_none(self):
        import app.utils.db as db_module
        original = db_module._mongo_db
        db_module._mongo_db = None
        assert db_module.get_db() is None
        db_module._mongo_db = original  # restore

    def test_get_redis_before_connect_returns_none(self):
        import app.utils.db as db_module
        original = db_module._redis_client
        db_module._redis_client = None
        assert db_module.get_redis() is None
        db_module._redis_client = original

    @pytest.mark.asyncio
    async def test_connect_mongo_calls_motor(self):
        with patch("app.utils.db.motor.motor_asyncio.AsyncIOMotorClient") as mock_client:
            mock_db = MagicMock()
            mock_db.events_raw.create_index = AsyncMock()
            mock_db.recruiter_dash_rollups.create_index = AsyncMock()
            mock_db.member_dash_rollups.create_index = AsyncMock()
            mock_db.benchmark_runs.create_index = AsyncMock()
            mock_client.return_value.__getitem__ = MagicMock(return_value=mock_db)
            import app.utils.db as db_module
            await db_module.connect_mongo()
            mock_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_redis_calls_ping(self):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        with patch("app.utils.db.aioredis.from_url", return_value=mock_redis):
            import app.utils.db as db_module
            await db_module.connect_redis()
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_connections(self):
        import app.utils.db as db_module
        mock_mongo = MagicMock()
        mock_redis = AsyncMock()
        db_module._mongo_client = mock_mongo
        db_module._redis_client = mock_redis
        await db_module.close_connections()
        mock_mongo.close.assert_called_once()
        mock_redis.close.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4: app/services/analytics_service.py
# What it does: core business logic — ingest, rollups, queries, benchmarks
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_db():
    """Returns a mock MongoDB database object with all collection methods."""
    db = MagicMock()
    db.events_raw.find_one = AsyncMock(return_value=None)
    db.events_raw.insert_one = AsyncMock()
    db.events_raw.count_documents = AsyncMock(return_value=0)
    db.events_raw.aggregate = MagicMock(return_value=_async_iter([]))
    db.recruiter_dash_rollups.update_one = AsyncMock()
    db.recruiter_dash_rollups.aggregate = MagicMock(return_value=_async_iter([]))
    db.member_dash_rollups.update_one = AsyncMock()
    db.member_dash_rollups.aggregate = MagicMock(return_value=_async_iter([]))
    db.benchmark_runs.insert_one = AsyncMock()
    return db


def _async_iter(items):
    """Creates an async iterable from a list — used to mock .aggregate()."""
    class AsyncIterator:
        def __init__(self, data):
            self._data = iter(data)
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self._data)
            except StopIteration:
                raise StopAsyncIteration
    return AsyncIterator(items)


def _make_mock_redis(cached=None):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=cached)
    redis.setex = AsyncMock()
    return redis


@pytest.mark.asyncio
class TestAnalyticsService:

    # ── ingest_event ──────────────────────────────────────────────────

    async def test_ingest_stores_event_and_returns_accepted(self):
        from app.models.events import EventIngestRequest, EntityRef
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = EventIngestRequest(
            event_type="job.viewed",
            actor_id="mem_100",
            entity=EntityRef(entity_type="job", entity_id="job_001"),
            payload={"location": "Austin, TX"},
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_producer", new_callable=AsyncMock) as mock_prod:
            mock_prod.return_value.send_and_wait = AsyncMock()
            result = await svc.ingest_event(req)

        assert result.accepted is True
        assert result.event_id.startswith("evt_")
        mock_db.events_raw.insert_one.assert_called_once()

    async def test_ingest_idempotency_raises_409_on_duplicate(self):
        from fastapi import HTTPException
        from app.models.events import EventIngestRequest, EntityRef
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        mock_db.events_raw.find_one = AsyncMock(
            return_value={"event_id": "evt_existing_abc", "idempotency_key": "idem_xyz"}
        )
        req = EventIngestRequest(
            event_type="job.viewed",
            actor_id="mem_100",
            entity=EntityRef(entity_type="job", entity_id="job_001"),
            idempotency_key="idem_xyz",
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db):
            with pytest.raises(HTTPException) as exc_info:
                await svc.ingest_event(req)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["original_event_id"] == "evt_existing_abc"
        mock_db.events_raw.insert_one.assert_not_called()

    async def test_ingest_kafka_failure_does_not_raise(self):
        """Kafka publish failure should log a warning, not crash ingest."""
        from app.models.events import EventIngestRequest, EntityRef
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = EventIngestRequest(
            event_type="job.viewed",
            actor_id="mem_100",
            entity=EntityRef(entity_type="job", entity_id="job_001"),
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_producer", side_effect=Exception("Kafka down")):
            result = await svc.ingest_event(req)

        assert result.accepted is True  # must still succeed

    # ── _update_rollups ───────────────────────────────────────────────

    async def test_rollup_job_viewed_updates_recruiter_dash(self):
        from app.models.events import EventIngestRequest, EntityRef
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = EventIngestRequest(
            event_type="job.viewed",
            actor_id="mem_100",
            entity=EntityRef(entity_type="job", entity_id="job_777"),
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db):
            await svc._update_rollups(req, datetime.utcnow())

        mock_db.recruiter_dash_rollups.update_one.assert_called_once()
        call_args = mock_db.recruiter_dash_rollups.update_one.call_args
        assert call_args[0][0]["job_id"] == "job_777"
        assert "$inc" in call_args[0][1]

    async def test_rollup_application_submitted_updates_both_dashes(self):
        from app.models.events import EventIngestRequest, EntityRef
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = EventIngestRequest(
            event_type="application.submitted",
            actor_id="mem_200",
            entity=EntityRef(entity_type="application", entity_id="app_001"),
            payload={"job_id": "job_888", "member_id": "mem_200"},
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db):
            await svc._update_rollups(req, datetime.utcnow())

        # Both recruiter and member dashboards must be updated
        assert mock_db.recruiter_dash_rollups.update_one.call_count == 1
        assert mock_db.member_dash_rollups.update_one.call_count == 1

    async def test_rollup_message_sent_updates_receiver(self):
        from app.models.events import EventIngestRequest, EntityRef
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = EventIngestRequest(
            event_type="message.sent",
            actor_id="mem_111",
            entity=EntityRef(entity_type="thread", entity_id="thr_001"),
            payload={"receiver_id": "mem_222"},
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db):
            await svc._update_rollups(req, datetime.utcnow())

        call_args = mock_db.member_dash_rollups.update_one.call_args
        assert call_args[0][0]["member_id"] == "mem_222"

    async def test_rollup_connection_accepted_updates_both_members(self):
        from app.models.events import EventIngestRequest, EntityRef
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = EventIngestRequest(
            event_type="connection.accepted",
            actor_id="mem_111",
            entity=EntityRef(entity_type="connection", entity_id="conn_001"),
            payload={"receiver_id": "mem_333"},
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db):
            await svc._update_rollups(req, datetime.utcnow())

        assert mock_db.member_dash_rollups.update_one.call_count == 2

    async def test_rollup_profile_viewed_updates_viewed_member(self):
        from app.models.events import EventIngestRequest, EntityRef
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = EventIngestRequest(
            event_type="profile.viewed",
            actor_id="mem_001",
            entity=EntityRef(entity_type="member", entity_id="mem_999"),
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db):
            await svc._update_rollups(req, datetime.utcnow())

        call_args = mock_db.member_dash_rollups.update_one.call_args
        assert call_args[0][0]["member_id"] == "mem_999"

    # ── get_top_jobs ──────────────────────────────────────────────────

    async def test_top_jobs_returns_from_cache(self):
        from app.models.events import TopJobsRequest
        import app.services.analytics_service as svc

        cached_data = [{"job_id": "job_001", "count": 99}]
        mock_redis = _make_mock_redis(cached=json.dumps(cached_data))
        mock_db = _make_mock_db()

        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_redis", return_value=mock_redis):
            result = await svc.get_top_jobs(TopJobsRequest(metric="applications", limit=5))

        assert result == cached_data
        mock_db.recruiter_dash_rollups.aggregate.assert_not_called()  # skipped DB

    async def test_top_jobs_queries_db_on_cache_miss(self):
        from app.models.events import TopJobsRequest
        import app.services.analytics_service as svc

        db_result = [{"_id": "job_042", "total": 15}]
        mock_db = _make_mock_db()
        mock_db.recruiter_dash_rollups.aggregate = MagicMock(return_value=_async_iter(db_result))
        mock_redis = _make_mock_redis(cached=None)

        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_redis", return_value=mock_redis), \
             patch("app.services.analytics_service.get_settings") as mock_settings:
            mock_settings.return_value.REDIS_CACHE_TTL = 300
            result = await svc.get_top_jobs(TopJobsRequest(metric="applications", limit=5))

        assert result == [{"job_id": "job_042", "count": 15}]
        mock_redis.setex.assert_called_once()  # result was cached

    # ── get_funnel ────────────────────────────────────────────────────

    async def test_funnel_calculates_rates_correctly(self):
        from app.models.events import FunnelRequest
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        mock_db.events_raw.count_documents = AsyncMock(side_effect=[100, 40, 20])
        mock_redis = _make_mock_redis(cached=None)

        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_redis", return_value=mock_redis), \
             patch("app.services.analytics_service.get_settings") as mock_settings:
            mock_settings.return_value.REDIS_CACHE_TTL = 300
            result = await svc.get_funnel(FunnelRequest(days=30))

        assert result.views == 100
        assert result.saves == 40
        assert result.applications == 20
        assert result.view_to_save_rate == 0.4
        assert result.save_to_apply_rate == 0.5
        assert result.view_to_apply_rate == 0.2

    async def test_funnel_zero_views_avoids_division_by_zero(self):
        from app.models.events import FunnelRequest
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        mock_db.events_raw.count_documents = AsyncMock(side_effect=[0, 0, 0])
        mock_redis = _make_mock_redis(cached=None)

        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_redis", return_value=mock_redis), \
             patch("app.services.analytics_service.get_settings") as mock_settings:
            mock_settings.return_value.REDIS_CACHE_TTL = 300
            result = await svc.get_funnel(FunnelRequest(days=30))

        assert result.view_to_apply_rate == 0
        assert result.view_to_save_rate == 0

    # ── get_geo ───────────────────────────────────────────────────────

    async def test_geo_returns_cached_result(self):
        from app.models.events import GeoRequest
        import app.services.analytics_service as svc

        cached = [{"location": "San Jose, CA", "count": 42}]
        mock_redis = _make_mock_redis(cached=json.dumps(cached))
        mock_db = _make_mock_db()

        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_redis", return_value=mock_redis):
            result = await svc.get_geo(GeoRequest())

        assert result == cached

    async def test_geo_aggregates_from_db_on_miss(self):
        from app.models.events import GeoRequest
        import app.services.analytics_service as svc

        db_result = [{"_id": "Austin, TX", "count": 5}]
        mock_db = _make_mock_db()
        mock_db.events_raw.aggregate = MagicMock(return_value=_async_iter(db_result))
        mock_redis = _make_mock_redis(cached=None)

        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_redis", return_value=mock_redis), \
             patch("app.services.analytics_service.get_settings") as mock_settings:
            mock_settings.return_value.REDIS_CACHE_TTL = 300
            result = await svc.get_geo(GeoRequest())

        assert result == [{"location": "Austin, TX", "count": 5}]

    # ── get_member_dashboard ──────────────────────────────────────────

    async def test_member_dashboard_returns_zeros_for_unknown_member(self):
        from app.models.events import MemberDashboardRequest
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        mock_db.member_dash_rollups.aggregate = MagicMock(return_value=_async_iter([]))

        with patch("app.services.analytics_service.get_db", return_value=mock_db):
            result = await svc.get_member_dashboard(MemberDashboardRequest(member_id="mem_nobody"))

        assert result.profile_views == 0
        assert result.applications_sent == 0
        assert result.connections == 0
        assert result.messages_received == 0

    async def test_member_dashboard_sums_rollups(self):
        from app.models.events import MemberDashboardRequest
        import app.services.analytics_service as svc

        agg_result = [{
            "_id": None,
            "profile_views": 7,
            "applications_sent": 3,
            "connections": 12,
            "messages_received": 5,
        }]
        mock_db = _make_mock_db()
        mock_db.member_dash_rollups.aggregate = MagicMock(return_value=_async_iter(agg_result))

        with patch("app.services.analytics_service.get_db", return_value=mock_db):
            result = await svc.get_member_dashboard(MemberDashboardRequest(member_id="mem_100"))

        assert result.profile_views == 7
        assert result.connections == 12

    # ── store_benchmark ───────────────────────────────────────────────

    async def test_benchmark_stores_and_returns_id(self):
        from app.models.events import BenchmarkReportRequest
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = BenchmarkReportRequest(
            scenario="A", owner_id="owner7", service_name="analytics",
            results={"p50_ms": 10, "p99_ms": 45}, metadata={},
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_producer", new_callable=AsyncMock) as mock_prod:
            mock_prod.return_value.send_and_wait = AsyncMock()
            result = await svc.store_benchmark(req)

        assert result.benchmark_id.startswith("bench_")
        assert result.status == "stored"
        mock_db.benchmark_runs.insert_one.assert_called_once()

    async def test_benchmark_kafka_failure_still_stores(self):
        from app.models.events import BenchmarkReportRequest
        import app.services.analytics_service as svc

        mock_db = _make_mock_db()
        req = BenchmarkReportRequest(
            scenario="B", owner_id="owner7", service_name="analytics",
            results={"rps": 1000},
        )
        with patch("app.services.analytics_service.get_db", return_value=mock_db), \
             patch("app.services.analytics_service.get_producer", side_effect=Exception("Kafka down")):
            result = await svc.store_benchmark(req)

        assert result.status == "stored"  # must succeed even if Kafka is down


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5: app/consumers/event_consumer.py
# What it does: Kafka consumer — reads topics, calls rollup updates
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestEventConsumer:

    async def test_process_event_stores_raw_and_calls_rollup(self):
        from app.consumers.event_consumer import _process_event

        mock_db = _make_mock_db()
        event = {
            "event_type": "job.viewed",
            "trace_id": "trc_abc",
            "timestamp": datetime.utcnow().isoformat(),
            "actor_id": "mem_100",
            "entity": {"entity_type": "job", "entity_id": "job_500"},
            "payload": {"location": "Seattle, WA"},
            "idempotency_key": "idem_fresh_001",
        }
        with patch("app.consumers.event_consumer.get_db", return_value=mock_db):
            await _process_event("job.viewed", event)

        mock_db.events_raw.insert_one.assert_called_once()
        mock_db.recruiter_dash_rollups.update_one.assert_called_once()

    async def test_process_event_skips_duplicate_idempotency_key(self):
        from app.consumers.event_consumer import _process_event

        mock_db = _make_mock_db()
        mock_db.events_raw.find_one = AsyncMock(
            return_value={"event_id": "evt_existing", "idempotency_key": "idem_dup"}
        )
        event = {
            "trace_id": "trc_dup",
            "timestamp": datetime.utcnow().isoformat(),
            "actor_id": "mem_100",
            "entity": {},
            "payload": {},
            "idempotency_key": "idem_dup",
        }
        with patch("app.consumers.event_consumer.get_db", return_value=mock_db):
            await _process_event("job.viewed", event)

        # Must not insert or update anything
        mock_db.events_raw.insert_one.assert_not_called()
        mock_db.recruiter_dash_rollups.update_one.assert_not_called()

    async def test_process_event_without_idempotency_key_always_stores(self):
        from app.consumers.event_consumer import _process_event

        mock_db = _make_mock_db()
        event = {
            "trace_id": "trc_no_idem",
            "timestamp": datetime.utcnow().isoformat(),
            "actor_id": "rec_100",
            "entity": {"entity_type": "job", "entity_id": "job_001"},
            "payload": {},
            # no idempotency_key
        }
        with patch("app.consumers.event_consumer.get_db", return_value=mock_db):
            await _process_event("job.created", event)

        mock_db.events_raw.insert_one.assert_called_once()

    async def test_rollup_from_kafka_application_submitted(self):
        from app.consumers.event_consumer import _update_rollup_from_kafka

        mock_db = _make_mock_db()
        event = {
            "actor_id": "mem_200",
            "entity": {"entity_type": "application", "entity_id": "app_001"},
            "payload": {"job_id": "job_999", "member_id": "mem_200"},
        }
        await _update_rollup_from_kafka("application.submitted", event, mock_db)

        assert mock_db.recruiter_dash_rollups.update_one.call_count == 1
        assert mock_db.member_dash_rollups.update_one.call_count == 1

    async def test_rollup_from_kafka_ai_events(self):
        from app.consumers.event_consumer import _update_rollup_from_kafka

        mock_db = _make_mock_db()
        event = {
            "actor_id": "rec_100",
            "entity": {"entity_type": "ai_task", "entity_id": "ait_001"},
            "payload": {"job_id": "job_777"},
        }
        for ai_event in ["ai.requested", "ai.completed", "ai.approved", "ai.rejected"]:
            mock_db.recruiter_dash_rollups.update_one.reset_mock()
            await _update_rollup_from_kafka(ai_event, event, mock_db)
            mock_db.recruiter_dash_rollups.update_one.assert_called_once()

    async def test_rollup_from_kafka_connection_accepted_updates_both(self):
        from app.consumers.event_consumer import _update_rollup_from_kafka

        mock_db = _make_mock_db()
        event = {
            "actor_id": "mem_aaa",
            "entity": {},
            "payload": {"receiver_id": "mem_bbb"},
        }
        await _update_rollup_from_kafka("connection.accepted", event, mock_db)
        assert mock_db.member_dash_rollups.update_one.call_count == 2

    async def test_rollup_from_kafka_message_sent_updates_receiver_only(self):
        from app.consumers.event_consumer import _update_rollup_from_kafka

        mock_db = _make_mock_db()
        event = {
            "actor_id": "mem_sender",
            "entity": {},
            "payload": {"receiver_id": "mem_receiver"},
        }
        await _update_rollup_from_kafka("message.sent", event, mock_db)

        assert mock_db.member_dash_rollups.update_one.call_count == 1
        call_args = mock_db.member_dash_rollups.update_one.call_args
        assert call_args[0][0]["member_id"] == "mem_receiver"

    async def test_subscribed_topics_count(self):
        from app.consumers.event_consumer import SUBSCRIBED_TOPICS
        # Sanity check — must have all 8 owners' topics covered
        assert len(SUBSCRIBED_TOPICS) >= 22
        assert "job.viewed" in SUBSCRIBED_TOPICS
        assert "application.submitted" in SUBSCRIBED_TOPICS
        assert "ai.completed" in SUBSCRIBED_TOPICS
        assert "connection.accepted" in SUBSCRIBED_TOPICS
