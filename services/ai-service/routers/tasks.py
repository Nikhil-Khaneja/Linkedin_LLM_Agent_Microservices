from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime
import uuid, json

from models.task import CreateTaskRequest, ApproveTaskRequest, RejectTaskRequest
from utils.auth import verify_token

router = APIRouter()

@router.post("/create")
async def create_task(body: CreateTaskRequest, request: Request, user=Depends(verify_token)):
    db = request.app.state.db
    kafka = request.app.state.kafka
    trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
    task_id = "task_" + uuid.uuid4().hex[:16]
    normalized_task_type = "full_pipeline" if body.task_type == "shortlist_and_outreach" else body.task_type
    doc = {
        "task_id": task_id, "recruiter_id": user["userId"], "job_id": body.job_id,
        "task_type": normalized_task_type, "requested_task_type": body.task_type,
        "status": "queued", "trace_id": trace_id,
        "steps": [], "current_step": "queued", "input_payload": body.parameters or {},
        "auth_token": request.headers.get("authorization", ""),
        "output": {}, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    }
    await db.agent_tasks.insert_one(doc)
    await kafka.send_and_wait("ai.requests", json.dumps({
        "task_id": task_id,
        "event_type": "ai.requested", "trace_id": trace_id,
        "timestamp": datetime.utcnow().isoformat(), "actor_id": user["userId"],
        "entity": {"entity_type": "ai_task", "entity_id": task_id},
        "payload": {"task_id": task_id, "job_id": body.job_id, "task_type": normalized_task_type},
        "idempotency_key": task_id,
    }).encode())
    return {"success": True, "trace_id": trace_id, "data": {"task_id": task_id, "status": "queued"}}

@router.get("/{task_id}")
async def get_task(task_id: str, request: Request, user=Depends(verify_token)):
    db = request.app.state.db
    task = await db.agent_tasks.find_one({"task_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task["_id"] = str(task["_id"])
    return {"success": True, "trace_id": request.headers.get("x-trace-id",""), "data": task}

@router.post("/{task_id}/approve")
async def approve_task(task_id: str, body: ApproveTaskRequest, request: Request, user=Depends(verify_token)):
    db = request.app.state.db
    kafka = request.app.state.kafka
    broadcast = request.app.state.broadcast
    task = await db.agent_tasks.find_one({"task_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    upd = {"status": "approved", "approved_by": user["userId"], "updated_at": datetime.utcnow()}
    if body.note:
        upd["approval_note"] = body.note
    if body.edits:
        upd["output"] = {**(task.get("output") or {}), "recruiter_edits": body.edits}
    await db.agent_tasks.update_one({"task_id": task_id}, {"$set": upd})
    await kafka.send_and_wait("ai.results", json.dumps({
        "event_type": "ai.approved", "trace_id": task.get("trace_id"),
        "timestamp": datetime.utcnow().isoformat(), "actor_id": user["userId"],
        "entity": {"entity_type": "ai_task", "entity_id": task_id},
        "payload": {"task_id": task_id, "status": "approved"},
        "idempotency_key": task_id + "_approval",
    }).encode())
    await broadcast(task_id, {"type": "approved", "task_id": task_id})
    return {"success": True, "data": {"task_id": task_id, "status": "approved"}}

@router.post("/{task_id}/reject")
async def reject_task(task_id: str, body: RejectTaskRequest, request: Request, user=Depends(verify_token)):
    db = request.app.state.db
    kafka = request.app.state.kafka
    broadcast = request.app.state.broadcast
    task = await db.agent_tasks.find_one({"task_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.agent_tasks.update_one({"task_id": task_id}, {"$set": {
        "status": "rejected", "error_message": body.reason, "updated_at": datetime.utcnow()}})
    await kafka.send_and_wait("ai.results", json.dumps({
        "event_type": "ai.rejected", "trace_id": task.get("trace_id"),
        "timestamp": datetime.utcnow().isoformat(), "actor_id": user["userId"],
        "entity": {"entity_type": "ai_task", "entity_id": task_id},
        "payload": {"task_id": task_id, "status": "rejected", "reason": body.reason},
        "idempotency_key": task_id + "_rejection",
    }).encode())
    await broadcast(task_id, {"type": "rejected", "task_id": task_id, "reason": body.reason})
    return {"success": True, "data": {"task_id": task_id, "status": "rejected"}}


@router.get("/metrics/approval-rate")
async def approval_rate(request: Request, user=Depends(verify_token)):
    db = request.app.state.db
    total_reviewed = await db.agent_tasks.count_documents({"status": {"$in": ["approved", "rejected"]}})
    approved = await db.agent_tasks.count_documents({"status": "approved"})
    rejected = await db.agent_tasks.count_documents({"status": "rejected"})
    rate = round((approved / total_reviewed) * 100, 2) if total_reviewed else 0.0
    return {
        "success": True,
        "data": {
            "approval_rate_pct": rate,
            "approved_count": approved,
            "rejected_count": rejected,
            "reviewed_count": total_reviewed
        }
    }
