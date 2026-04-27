"""
Standard Kafka event envelope + specific event models.
Every owner must follow this envelope format.
"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum


# ── Standard Kafka Envelope (shared contract) ─────────────────────

class EntityRef(BaseModel):
    entity_type: str
    entity_id: str


class KafkaEventEnvelope(BaseModel):
    """The universal event format all 8 owners agreed on."""
    event_type: str
    trace_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor_id: str
    entity: EntityRef
    payload: dict = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


# ── Ingest request / response ─────────────────────────────────────

class EventIngestRequest(BaseModel):
    event_type: str
    actor_id: str
    entity: EntityRef
    trace_id: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class EventIngestResponse(BaseModel):
    accepted: bool
    event_id: str


# ── Analytics query models ────────────────────────────────────────

class TopJobsRequest(BaseModel):
    metric: str = "applications"  # applications | views | saves
    limit: int = 10
    days: int = 30


class FunnelRequest(BaseModel):
    job_id: Optional[str] = None
    days: int = 30


class FunnelResponse(BaseModel):
    views: int
    saves: int
    applications: int
    view_to_save_rate: float
    save_to_apply_rate: float
    view_to_apply_rate: float


class GeoRequest(BaseModel):
    job_id: Optional[str] = None       # filter to a specific job
    city: Optional[str] = None         # filter to a specific city (e.g. "San Jose")
    state: Optional[str] = None        # filter to a specific state (e.g. "CA")
    event_type: Optional[str] = None   # filter to "job.viewed" or "application.submitted"
    days: int = 30                     # lookback window in days
    limit: int = 20                    # max locations returned


class MemberDashboardRequest(BaseModel):
    member_id: str


class MemberDashboardResponse(BaseModel):
    profile_views: int
    applications_sent: int
    connections: int
    messages_received: int
    job_matches: int


class BenchmarkReportRequest(BaseModel):
    scenario: str  # "A" or "B"
    owner_id: str
    service_name: str
    results: dict
    metadata: dict = Field(default_factory=dict)


class BenchmarkReportResponse(BaseModel):
    benchmark_id: str
    status: str
