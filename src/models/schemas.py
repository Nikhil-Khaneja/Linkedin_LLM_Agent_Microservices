"""
Pydantic models for Job Service API requests and responses
Based on the API documentation specifications
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


# ============================================
# ENUMS
# ============================================
class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class JobStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    DRAFT = "draft"


class SortOrder(str, Enum):
    RELEVANCE = "relevance"
    NEWEST = "newest"
    OLDEST = "oldest"


# ============================================
# SHARED MODELS
# ============================================
class SalaryRange(BaseModel):
    """Salary range for job posting"""
    min: Optional[float] = Field(None, ge=0, description="Minimum salary")
    max: Optional[float] = Field(None, ge=0, description="Maximum salary")
    currency: str = Field("USD", max_length=3, description="Currency code")


class Pagination(BaseModel):
    """Pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=50, description="Page size")


# ============================================
# REQUEST MODELS
# ============================================
class CreateJobRequest(BaseModel):
    """Request body for POST /jobs/create"""
    company_id: str = Field(..., pattern=r"^cmp_\w+$", description="Company ID")
    recruiter_id: str = Field(..., pattern=r"^rec_\w+$", description="Recruiter ID")
    title: str = Field(..., min_length=1, max_length=160, description="Job title")
    description: str = Field(..., min_length=30, description="Job description")
    seniority_level: SeniorityLevel = Field(SeniorityLevel.MID, description="Seniority level")
    employment_type: EmploymentType = Field(EmploymentType.FULL_TIME, description="Employment type")
    location: str = Field(..., max_length=120, description="Job location")
    work_mode: WorkMode = Field(WorkMode.ONSITE, description="Work mode")
    skills_required: List[str] = Field(..., min_length=1, max_length=30, description="Required skills")
    salary_range: Optional[SalaryRange] = Field(None, description="Salary range")

    @field_validator('skills_required')
    @classmethod
    def validate_skills(cls, v):
        if len(v) < 1 or len(v) > 30:
            raise ValueError('skills_required must have 1-30 skills')
        return [skill.strip() for skill in v if skill.strip()]


class GetJobRequest(BaseModel):
    """Request body for POST /jobs/get"""
    job_id: str = Field(..., pattern=r"^job_\w+$", description="Job ID")
    viewer_id: Optional[str] = Field(None, description="Viewer ID for analytics")


class UpdateJobRequest(BaseModel):
    """Request body for POST /jobs/update"""
    job_id: str = Field(..., pattern=r"^job_\w+$", description="Job ID")
    recruiter_id: str = Field(..., pattern=r"^rec_\w+$", description="Recruiter ID")
    expected_version: Optional[int] = Field(None, ge=1, description="Optimistic lock version")
    title: Optional[str] = Field(None, min_length=1, max_length=160)
    description: Optional[str] = Field(None, min_length=30)
    seniority_level: Optional[SeniorityLevel] = None
    employment_type: Optional[EmploymentType] = None
    location: Optional[str] = Field(None, max_length=120)
    work_mode: Optional[WorkMode] = None
    skills_required: Optional[List[str]] = Field(None, max_length=30)
    salary_range: Optional[SalaryRange] = None


class SearchJobRequest(BaseModel):
    """Request body for POST /jobs/search"""
    keyword: Optional[str] = Field(None, max_length=120, description="Search keyword")
    location: Optional[str] = Field(None, max_length=120, description="Location filter")
    employment_type: Optional[EmploymentType] = Field(None, description="Employment type filter")
    seniority_level: Optional[SeniorityLevel] = Field(None, description="Seniority filter")
    work_mode: Optional[WorkMode] = Field(None, description="Work mode filter")
    skills: Optional[List[str]] = Field(None, description="Skills filter")
    salary_min: Optional[float] = Field(None, ge=0, description="Minimum salary")
    industry: Optional[str] = Field(None, max_length=80, description="Industry filter")
    remote: Optional[bool] = Field(None, description="Remote only filter")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=50, description="Page size")
    sort: SortOrder = Field(SortOrder.RELEVANCE, description="Sort order")


class CloseJobRequest(BaseModel):
    """Request body for POST /jobs/close"""
    job_id: str = Field(..., pattern=r"^job_\w+$", description="Job ID")
    recruiter_id: str = Field(..., pattern=r"^rec_\w+$", description="Recruiter ID")
    reason: Optional[str] = Field("", max_length=500, description="Reason for closing")


class JobsByRecruiterRequest(BaseModel):
    """Request body for POST /jobs/byRecruiter"""
    recruiter_id: str = Field(..., pattern=r"^rec_\w+$", description="Recruiter ID")
    status: Optional[JobStatus] = Field(None, description="Filter by status")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=50, description="Page size")


class SaveJobRequest(BaseModel):
    """Request body for POST /jobs/save"""
    job_id: str = Field(..., pattern=r"^job_\w+$", description="Job ID")
    member_id: str = Field(..., pattern=r"^mem_\w+$", description="Member ID")


class UnsaveJobRequest(BaseModel):
    """Request body for POST /jobs/unsave"""
    job_id: str = Field(..., pattern=r"^job_\w+$", description="Job ID")
    member_id: str = Field(..., pattern=r"^mem_\w+$", description="Member ID")


class SavedJobsByMemberRequest(BaseModel):
    """Request body for POST /jobs/savedByMember"""
    member_id: str = Field(..., pattern=r"^mem_\w+$", description="Member ID")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=50, description="Page size")


class JobStatusRequest(BaseModel):
    """Request body for POST /jobs/status (internal API for Owner 5)"""
    job_id: str = Field(..., pattern=r"^job_\w+$", description="Job ID")


# ============================================
# RESPONSE MODELS
# ============================================
class JobSummary(BaseModel):
    """Job summary for list views"""
    job_id: str
    title: str
    company_id: str
    location: str
    employment_type: str
    work_mode: str
    seniority_level: str
    posted_datetime: datetime
    status: str
    views_count: int = 0
    applicants_count: int = 0
    saves_count: int = 0


class JobDetail(BaseModel):
    """Full job detail"""
    job_id: str
    company_id: str
    recruiter_id: str
    title: str
    description: str
    seniority_level: str
    employment_type: str
    location: str
    work_mode: str
    skills_required: List[str]
    salary_range: Optional[SalaryRange] = None
    posted_datetime: datetime
    updated_datetime: datetime
    status: str
    views_count: int = 0
    applicants_count: int = 0
    saves_count: int = 0
    version: int = 1


class CreateJobResponse(BaseModel):
    """Response for POST /jobs/create"""
    job_id: str
    status: str
    recruiter_id: str


class GetJobResponse(BaseModel):
    """Response for POST /jobs/get"""
    job: JobDetail


class UpdateJobResponse(BaseModel):
    """Response for POST /jobs/update"""
    job_id: str
    updated: bool
    version: int


class SearchJobResponse(BaseModel):
    """Response for POST /jobs/search"""
    items: List[JobSummary]


class CloseJobResponse(BaseModel):
    """Response for POST /jobs/close"""
    job_id: str
    status: str
    closed_datetime: datetime


class JobsByRecruiterResponse(BaseModel):
    """Response for POST /jobs/byRecruiter"""
    jobs: List[JobSummary]


class SaveJobResponse(BaseModel):
    """Response for POST /jobs/save"""
    saved: bool
    saved_at: datetime


class JobStatusResponse(BaseModel):
    """Response for POST /jobs/status"""
    job_id: str
    status: str
    closed_datetime: Optional[datetime] = None


# ============================================
# API ENVELOPE MODELS
# ============================================
class MetaInfo(BaseModel):
    """Metadata for responses"""
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
    cache: Optional[Literal["hit", "miss"]] = None


class SuccessResponse(BaseModel):
    """Standard success response envelope"""
    success: bool = True
    trace_id: str
    data: dict
    meta: Optional[MetaInfo] = None


class ErrorDetail(BaseModel):
    """Error details"""
    code: str
    message: str
    details: Optional[dict] = None
    retryable: bool = False


class ErrorResponse(BaseModel):
    """Standard error response envelope"""
    success: bool = False
    trace_id: str
    error: ErrorDetail
