"""
applications.py — Route handlers for Owner 5 Application Service.
Routes are thin; all business logic lives in application_service.py.
All /applications/* endpoints require a valid Bearer token.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import verify_token
from app.schemas import (
    SubmitApplicationRequest,  SubmitApplicationResponse,
    GetApplicationRequest,     ApplicationOut,
    ByJobRequest,
    ByMemberRequest,
    UpdateStatusRequest,       UpdateStatusResponse,
    AddNoteRequest,            AddNoteResponse,
)
from app.services.application_service import (
    submit_application,
    get_application,
    get_applications_by_job,
    get_applications_by_member,
    update_status,
    add_note,
)

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("/submit", response_model=SubmitApplicationResponse, status_code=201)
def submit(
    req: SubmitApplicationRequest,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """Submit a new job application."""
    return submit_application(req, db)


@router.post("/get", response_model=ApplicationOut)
def get(
    req: GetApplicationRequest,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """Get application details including answers and recruiter notes."""
    return get_application(req.application_id, db)


@router.post("/byJob", response_model=List[ApplicationOut])
def by_job(
    req: ByJobRequest,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """List all applications for a job (recruiter view)."""
    return get_applications_by_job(req.job_id, db)


@router.post("/byMember", response_model=List[ApplicationOut])
def by_member(
    req: ByMemberRequest,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """List all applications submitted by a member."""
    return get_applications_by_member(req.member_id, db)


@router.post("/updateStatus", response_model=UpdateStatusResponse)
def update(
    req: UpdateStatusRequest,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """Update application lifecycle status (recruiter action)."""
    return update_status(req, db)


@router.post("/addNote", response_model=AddNoteResponse, status_code=201)
def note(
    req: AddNoteRequest,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_token),
):
    """Add a recruiter note to an application."""
    return add_note(req, db)
