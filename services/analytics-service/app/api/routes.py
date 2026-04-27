"""
Owner 7 Analytics API — all 6 endpoints.
"""
from fastapi import APIRouter, HTTPException
from app.models.events import (
    EventIngestRequest, EventIngestResponse,
    TopJobsRequest, FunnelRequest, FunnelResponse,
    GeoRequest, MemberDashboardRequest, MemberDashboardResponse,
    BenchmarkReportRequest, BenchmarkReportResponse,
)
from app.services import analytics_service

router = APIRouter()


# ── Health check ───────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {"status": "ok", "service": "owner7-analytics"}


# ── 1. Event Ingest ───────────────────────────────────────────────
@router.post("/events/ingest", response_model=EventIngestResponse)
async def ingest_event(req: EventIngestRequest):
    """Receive UI and service events, store and republish normalized stream."""
    return await analytics_service.ingest_event(req)


# ── 2. Top Jobs ───────────────────────────────────────────────────
@router.post("/analytics/jobs/top")
async def top_jobs(req: TopJobsRequest):
    """Top jobs by applications/views/saves."""
    results = await analytics_service.get_top_jobs(req)
    return {"jobs": results, "metric": req.metric, "limit": req.limit}


# ── 3. View-Save-Apply Funnel ────────────────────────────────────
@router.post("/analytics/funnel", response_model=FunnelResponse)
async def funnel(req: FunnelRequest):
    """View -> Save -> Apply funnel metrics."""
    return await analytics_service.get_funnel(req)


# ── 4. Geo Distribution ──────────────────────────────────────────
@router.post("/analytics/geo")
async def geo(req: GeoRequest):
    """City/state distribution for selected job or all jobs."""
    results = await analytics_service.get_geo(req)
    return {"distribution": results}


# ── 5. Member Dashboard ──────────────────────────────────────────
@router.post("/analytics/member/dashboard", response_model=MemberDashboardResponse)
async def member_dashboard(req: MemberDashboardRequest):
    """Member dashboard metrics."""
    return await analytics_service.get_member_dashboard(req)


# ── 6. Benchmark Report ──────────────────────────────────────────
@router.post("/benchmarks/report", response_model=BenchmarkReportResponse)
async def benchmark_report(req: BenchmarkReportRequest):
    """Store benchmark run output. Publishes benchmark.completed."""
    return await analytics_service.store_benchmark(req)
