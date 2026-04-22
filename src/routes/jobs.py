"""
Job API Routes
All endpoints for Job Service (Owner 4)
"""
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from typing import Optional

from src.config.database import get_db
from src.config.redis_config import get_cache_service, CacheService
from src.config.kafka_config import get_event_producer, JobEventProducer
from src.config.settings import get_settings
from src.services.job_service import JobService
from src.models.schemas import (
    CreateJobRequest, GetJobRequest, UpdateJobRequest,
    SearchJobRequest, CloseJobRequest, JobsByRecruiterRequest,
    SaveJobRequest, UnsaveJobRequest, SavedJobsByMemberRequest,
    JobStatusRequest, MetaInfo
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def get_trace_id(x_trace_id: Optional[str] = Header(None)) -> str:
    """Get or generate trace ID"""
    return x_trace_id or f"trc_{uuid.uuid4().hex[:24]}"


def create_success_response(trace_id: str, data: dict, meta: Optional[dict] = None) -> dict:
    """Create standard success response"""
    response = {
        "success": True,
        "trace_id": trace_id,
        "data": data
    }
    if meta:
        response["meta"] = meta
    return response


def create_error_response(trace_id: str, code: str, message: str, details: dict = None, retryable: bool = False) -> dict:
    """Create standard error response"""
    return {
        "success": False,
        "trace_id": trace_id,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "retryable": retryable
        }
    }


# ============================================
# POST /jobs/create
# ============================================
@router.post("/create")
async def create_job(
    request: CreateJobRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    Create a new job posting.
    Publishes job.created event to Kafka.
    """
    job_service = JobService(db)
    cache_service = get_cache_service()
    event_producer = get_event_producer()

    try:
        # Create job
        result = await job_service.create_job(request.model_dump())

        # Publish Kafka event
        await event_producer.publish_job_created(
            job_id=result["job_id"],
            recruiter_id=request.recruiter_id,
            job_data={
                "title": request.title,
                "company_id": request.company_id,
                "location": request.location,
                "skills_required": request.skills_required
            },
            trace_id=trace_id
        )

        # Invalidate caches
        await cache_service.invalidate_recruiter_jobs(request.recruiter_id)

        logger.info(f"Job created: {result['job_id']}, trace_id: {trace_id}")

        return create_success_response(trace_id, result)

    except Exception as e:
        logger.error(f"Failed to create job: {e}, trace_id: {trace_id}")
        raise HTTPException(status_code=500, detail=create_error_response(
            trace_id, "internal_error", str(e), retryable=True
        ))


# ============================================
# POST /jobs/get
# ============================================
@router.post("/get")
async def get_job(
    request: GetJobRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    Get job details by ID.
    Uses Redis cache-aside pattern.
    Publishes job.viewed event when viewer_id is provided.
    """
    job_service = JobService(db)
    cache_service = get_cache_service()
    event_producer = get_event_producer()

    cache_key = f"job:detail:{request.job_id}"
    cache_status = "miss"

    # Try cache first
    cached_job = await cache_service.get(cache_key)
    if cached_job:
        cache_status = "hit"
        job_data = cached_job
    else:
        # Fetch from database
        job_data = await job_service.get_job(request.job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail=create_error_response(
                trace_id, "not_found", "Job posting does not exist."
            ))

        # Cache the result
        await cache_service.set(cache_key, job_data, ttl=settings.cache_ttl_job_detail)

    # Publish view event if viewer is provided
    if request.viewer_id:
        await event_producer.publish_job_viewed(
            job_id=request.job_id,
            viewer_id=request.viewer_id,
            trace_id=trace_id
        )
        # Increment view count (async, don't wait)
        try:
            await job_service.increment_view_count(request.job_id)
        except Exception as e:
            logger.warning(f"Failed to increment view count: {e}")

    return create_success_response(
        trace_id,
        {"job": job_data},
        meta={"cache": cache_status}
    )


# ============================================
# POST /jobs/update
# ============================================
@router.post("/update")
async def update_job(
    request: UpdateJobRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    Update job fields.
    Publishes job.updated event to Kafka.
    """
    job_service = JobService(db)
    cache_service = get_cache_service()
    event_producer = get_event_producer()

    # Build updates dict (only non-None values)
    updates = {}
    for field in ["title", "description", "seniority_level", "employment_type",
                  "location", "work_mode", "skills_required", "salary_range"]:
        value = getattr(request, field, None)
        if value is not None:
            if hasattr(value, 'model_dump'):
                updates[field] = value.model_dump()
            elif hasattr(value, 'value'):
                updates[field] = value.value
            else:
                updates[field] = value

    success, result = await job_service.update_job(
        job_id=request.job_id,
        recruiter_id=request.recruiter_id,
        updates=updates,
        expected_version=request.expected_version
    )

    if not success:
        error_code = result.get("error", "internal_error")
        status_code = {
            "not_found": 404,
            "forbidden": 403,
            "job_closed": 409,
            "version_conflict": 409
        }.get(error_code, 500)

        raise HTTPException(status_code=status_code, detail=create_error_response(
            trace_id, error_code, result.get("message", "Update failed"),
            details=result.get("details")
        ))

    # Publish Kafka event
    await event_producer.publish_job_updated(
        job_id=request.job_id,
        recruiter_id=request.recruiter_id,
        updated_fields=updates,
        trace_id=trace_id
    )

    # Invalidate cache
    await cache_service.invalidate_job(request.job_id)

    logger.info(f"Job updated: {request.job_id}, trace_id: {trace_id}")

    return create_success_response(trace_id, result)


# ============================================
# POST /jobs/search
# ============================================
@router.post("/search")
async def search_jobs(
    request: SearchJobRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    Search jobs with filters.
    Uses Redis caching for common queries.
    """
    job_service = JobService(db)
    cache_service = get_cache_service()

    # Generate cache key
    filters_dict = request.model_dump(exclude_none=True)
    cache_key = cache_service.generate_search_key(filters_dict, {"page": request.page, "page_size": request.page_size})
    cache_status = "miss"

    # Try cache
    cached_result = await cache_service.get(cache_key)
    if cached_result:
        cache_status = "hit"
        items = cached_result["items"]
        total = cached_result["total"]
    else:
        # Search database
        items, total = await job_service.search_jobs(
            keyword=request.keyword,
            location=request.location,
            employment_type=request.employment_type.value if request.employment_type else None,
            seniority_level=request.seniority_level.value if request.seniority_level else None,
            work_mode=request.work_mode.value if request.work_mode else None,
            skills=request.skills,
            salary_min=request.salary_min,
            remote=request.remote,
            page=request.page,
            page_size=request.page_size,
            sort=request.sort.value
        )

        # Cache results
        await cache_service.set(cache_key, {"items": items, "total": total}, ttl=settings.cache_ttl_job_search)

    return create_success_response(
        trace_id,
        {"items": items},
        meta={
            "page": request.page,
            "page_size": request.page_size,
            "total": total,
            "cache": cache_status
        }
    )


# ============================================
# POST /jobs/close
# ============================================
@router.post("/close")
async def close_job(
    request: CloseJobRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    Close a job posting.
    Publishes job.closed event to Kafka - CRITICAL for Owner 5.
    """
    job_service = JobService(db)
    cache_service = get_cache_service()
    event_producer = get_event_producer()

    success, result = await job_service.close_job(request.job_id, request.recruiter_id)

    if not success:
        error_code = result.get("error", "internal_error")
        status_code = {
            "not_found": 404,
            "forbidden": 403,
            "already_closed": 409
        }.get(error_code, 500)

        raise HTTPException(status_code=status_code, detail=create_error_response(
            trace_id, error_code, result.get("message", "Close failed")
        ))

    # CRITICAL: Publish job.closed event for Owner 5
    await event_producer.publish_job_closed(
        job_id=request.job_id,
        recruiter_id=request.recruiter_id,
        reason=request.reason or "",
        trace_id=trace_id
    )

    # Invalidate cache
    await cache_service.invalidate_job(request.job_id)

    logger.info(f"Job closed: {request.job_id}, trace_id: {trace_id}")

    return create_success_response(trace_id, result)


# ============================================
# POST /jobs/byRecruiter
# ============================================
@router.post("/byRecruiter")
async def get_jobs_by_recruiter(
    request: JobsByRecruiterRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    List jobs owned by a recruiter.
    """
    job_service = JobService(db)

    jobs, total = await job_service.get_jobs_by_recruiter(
        recruiter_id=request.recruiter_id,
        status=request.status.value if request.status else None,
        page=request.page,
        page_size=request.page_size
    )

    return create_success_response(
        trace_id,
        {"jobs": jobs},
        meta={
            "page": request.page,
            "page_size": request.page_size,
            "total": total
        }
    )


# ============================================
# POST /jobs/save
# ============================================
@router.post("/save")
async def save_job(
    request: SaveJobRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    Save a job for a member.
    Publishes job.saved event.
    """
    job_service = JobService(db)
    event_producer = get_event_producer()

    success, result = await job_service.save_job(request.job_id, request.member_id)

    if not success:
        error_code = result.get("error", "internal_error")
        status_code = {
            "not_found": 404,
            "already_saved": 409
        }.get(error_code, 500)

        raise HTTPException(status_code=status_code, detail=create_error_response(
            trace_id, error_code, result.get("message", "Save failed")
        ))

    # Publish event
    await event_producer.publish_job_saved(
        job_id=request.job_id,
        member_id=request.member_id,
        trace_id=trace_id
    )

    return create_success_response(trace_id, result)


# ============================================
# POST /jobs/unsave
# ============================================
@router.post("/unsave")
async def unsave_job(
    request: UnsaveJobRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    Remove a saved job for a member.
    """
    job_service = JobService(db)

    success = await job_service.unsave_job(request.job_id, request.member_id)

    if not success:
        raise HTTPException(status_code=404, detail=create_error_response(
            trace_id, "not_found", "Saved job not found"
        ))

    return create_success_response(trace_id, {"unsaved": True})


# ============================================
# POST /jobs/savedByMember
# ============================================
@router.post("/savedByMember")
async def get_saved_jobs_by_member(
    request: SavedJobsByMemberRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    List jobs saved by a member.
    """
    job_service = JobService(db)

    jobs, total = await job_service.get_saved_jobs_by_member(
        member_id=request.member_id,
        page=request.page,
        page_size=request.page_size
    )

    return create_success_response(
        trace_id,
        {"jobs": jobs},
        meta={
            "page": request.page,
            "page_size": request.page_size,
            "total": total
        }
    )


# ============================================
# POST /jobs/status (Internal API for Owner 5)
# ============================================
@router.post("/status")
async def get_job_status(
    request: JobStatusRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id)
):
    """
    Get job status.
    Internal API for Owner 5 (Application Service) to verify job status
    before accepting applications.
    """
    job_service = JobService(db)

    result = await job_service.get_job_status(request.job_id)

    if not result:
        raise HTTPException(status_code=404, detail=create_error_response(
            trace_id, "not_found", "Job not found"
        ))

    return create_success_response(trace_id, result)
