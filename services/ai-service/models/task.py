from pydantic import BaseModel
from typing import Optional, Dict, Any

class CreateTaskRequest(BaseModel):
    job_id: str
    task_type: str = "full_pipeline"  # includes contract alias: shortlist_and_outreach
    parameters: Optional[Dict[str, Any]] = {}

class ApproveTaskRequest(BaseModel):
    approved: bool = True
    edits: Optional[str] = None
    note: Optional[str] = None

class RejectTaskRequest(BaseModel):
    reason: str
