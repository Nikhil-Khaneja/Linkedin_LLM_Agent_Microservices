"""
application_service.py — All business logic for Owner 5 Application Service.
Routes call these functions; routes stay thin.
"""

import uuid
import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.models import Application, ApplicationAnswer, RecruiterNote, JobStatusProjection
from app.schemas import (
    SubmitApplicationRequest,
    UpdateStatusRequest,
    AddNoteRequest,
    ALLOWED_STATUSES,
)
from app.redis_client import get_redis, make_idem_key
from app.config import DEMO_ALLOW_UNKNOWN_JOB, REDIS_IDEMPOTENCY_TTL
import app.kafka.producer as producer

logger = logging.getLogger(__name__)


def _new_id(prefix: str) -> str:
    """Generate a short prefixed UUID-based ID."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# ── Submit Application ─────────────────────────────────────────────────────────

def submit_application(req: SubmitApplicationRequest, db: Session) -> dict:
    """
    Full submit flow:
    1. Validate required fields.
    2. Check job_status_projection — block if closed.
    3. Check Redis idempotency key.
    4. Insert into MySQL.
    5. Publish Kafka event (failure does NOT roll back DB).
    """
    application_id = _new_id("app_")
    trace_id       = _new_id("trc_")

    # ── 1. Check job status ───────────────────────────────────────────────────
    job_row = db.query(JobStatusProjection).filter_by(job_id=req.job_id).first()

    if job_row:
        if job_row.status == "closed":
            raise HTTPException(status_code=400, detail="Cannot apply to closed job")
    else:
        # Job not in local projection
        if not DEMO_ALLOW_UNKNOWN_JOB:
            raise HTTPException(status_code=404, detail="Job not found in projection")
        logger.warning(
            "job_id=%s not in job_status_projection. DEMO_ALLOW_UNKNOWN_JOB=true — allowing.",
            req.job_id,
        )

    # ── 2. Redis fast duplicate check ─────────────────────────────────────────
    redis = get_redis()
    idem_key = make_idem_key(req.member_id, req.job_id)
    if redis:
        try:
            if redis.exists(idem_key):
                raise HTTPException(
                    status_code=409,
                    detail="Duplicate application — already applied to this job",
                )
            # Reserve the key before inserting into MySQL
            redis.setex(idem_key, REDIS_IDEMPOTENCY_TTL, application_id)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Redis check failed: %s — falling back to MySQL only", exc)

    # ── 3. Insert application into MySQL ─────────────────────────────────────
    app_row = Application(
        application_id  = application_id,
        job_id          = req.job_id,
        member_id       = req.member_id,
        resume_ref      = req.resume_ref,
        status          = "submitted",
        idempotency_key = req.idempotency_key,
        trace_id        = trace_id,
    )
    db.add(app_row)

    # Insert optional answers
    for ans in (req.answers or []):
        db.add(ApplicationAnswer(
            answer_id      = _new_id("ans_"),
            application_id = application_id,
            question_key   = ans.question_key,
            answer_text    = ans.answer_text,
        ))

    try:
        db.commit()
        db.refresh(app_row)
    except IntegrityError:
        db.rollback()
        # MySQL UNIQUE(job_id, member_id) or UNIQUE(idempotency_key) violated
        if redis:
            try:
                redis.delete(idem_key)
            except Exception:
                pass
        raise HTTPException(
            status_code=409,
            detail="Duplicate application — already applied to this job",
        )

    # ── 4. Publish Kafka event (non-blocking) ─────────────────────────────────
    try:
        producer.publish_application_submitted(
            application_id  = application_id,
            job_id          = req.job_id,
            member_id       = req.member_id,
            resume_ref      = req.resume_ref,
            idempotency_key = req.idempotency_key,
            trace_id        = trace_id,
        )
    except Exception as exc:
        logger.error("Kafka publish failed (DB already committed): %s", exc)

    return {"application_id": application_id, "status": "submitted", "trace_id": trace_id}


# ── Get Application ────────────────────────────────────────────────────────────

def get_application(application_id: str, db: Session) -> Application:
    row = db.query(Application).filter_by(application_id=application_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    return row


# ── List by Job ────────────────────────────────────────────────────────────────

def get_applications_by_job(job_id: str, db: Session) -> List[Application]:
    return db.query(Application).filter_by(job_id=job_id).all()


# ── List by Member ─────────────────────────────────────────────────────────────

def get_applications_by_member(member_id: str, db: Session) -> List[Application]:
    return db.query(Application).filter_by(member_id=member_id).all()


# ── Update Status ──────────────────────────────────────────────────────────────

def update_status(req: UpdateStatusRequest, db: Session) -> dict:
    """
    Validate → store old_status → update → publish Kafka event.
    """
    if req.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{req.status}'. Allowed: {sorted(ALLOWED_STATUSES)}",
        )

    row = db.query(Application).filter_by(application_id=req.application_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = row.status
    trace_id   = _new_id("trc_")

    row.status    = req.status
    row.trace_id  = trace_id
    if req.updated_by:
        row.recruiter_id = req.updated_by
    db.commit()

    try:
        producer.publish_status_updated(
            application_id = req.application_id,
            old_status     = old_status,
            new_status     = req.status,
            updated_by     = req.updated_by,
            trace_id       = trace_id,
        )
    except Exception as exc:
        logger.error("Kafka publish failed (DB already committed): %s", exc)

    return {
        "application_id": req.application_id,
        "old_status":     old_status,
        "new_status":     req.status,
        "trace_id":       trace_id,
    }


# ── Add Recruiter Note ─────────────────────────────────────────────────────────

def add_note(req: AddNoteRequest, db: Session) -> dict:
    """
    Validate → insert note → publish Kafka event.
    """
    row = db.query(Application).filter_by(application_id=req.application_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    note_id  = _new_id("note_")
    trace_id = _new_id("trc_")

    db.add(RecruiterNote(
        note_id        = note_id,
        application_id = req.application_id,
        recruiter_id   = req.recruiter_id,
        note_text      = req.note_text,
    ))
    db.commit()

    try:
        producer.publish_note_added(
            application_id = req.application_id,
            note_id        = note_id,
            recruiter_id   = req.recruiter_id,
            trace_id       = trace_id,
        )
    except Exception as exc:
        logger.error("Kafka publish failed (DB already committed): %s", exc)

    return {"note_id": note_id, "application_id": req.application_id, "status": "note_added"}
