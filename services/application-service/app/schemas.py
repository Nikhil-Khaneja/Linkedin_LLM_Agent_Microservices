"""
schemas.py — Pydantic request/response models for Owner 5 API.
"""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Helpers ────────────────────────────────────────────────────────────────────

ALLOWED_STATUSES = {
    "submitted",
    "under_review",
    "shortlisted",
    "interview",
    "hired",
    "rejected",
    "withdrawn",
}


# ── Request bodies ─────────────────────────────────────────────────────────────

class AnswerIn(BaseModel):
    question_key: str
    answer_text:  str


class SubmitApplicationRequest(BaseModel):
    job_id:          str = Field(..., json_schema_extra={"example": "job_3301"})
    member_id:       str = Field(..., json_schema_extra={"example": "mem_501"})
    resume_ref:      Optional[str] = Field(None)
    idempotency_key: str = Field(..., json_schema_extra={"example": "mem501-job3301-v1"})
    answers:         Optional[List[AnswerIn]] = []


class GetApplicationRequest(BaseModel):
    application_id: str


class ByJobRequest(BaseModel):
    job_id: str


class ByMemberRequest(BaseModel):
    member_id: str


class UpdateStatusRequest(BaseModel):
    application_id: str
    status:         str
    updated_by:     str


class AddNoteRequest(BaseModel):
    application_id: str
    recruiter_id:   str
    note_text:      str


# ── Response bodies ────────────────────────────────────────────────────────────

class AnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer_id:    str
    question_key: Optional[str]
    answer_text:  Optional[str]


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    note_id:      str
    recruiter_id: str
    note_text:    str
    created_at:   Optional[datetime]


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id:  str
    job_id:          str
    member_id:       str
    recruiter_id:    Optional[str]
    resume_ref:      Optional[str]
    status:          str
    trace_id:        Optional[str]
    submitted_at:    Optional[datetime]
    updated_at:      Optional[datetime]
    answers:         List[AnswerOut] = []
    notes:           List[NoteOut]  = []


class SubmitApplicationResponse(BaseModel):
    application_id: str
    status:         str
    trace_id:       str


class UpdateStatusResponse(BaseModel):
    application_id: str
    old_status:     str
    new_status:     str
    trace_id:       str


class AddNoteResponse(BaseModel):
    note_id:        str
    application_id: str
    status:         str


class HealthResponse(BaseModel):
    service: str
    status:  str
