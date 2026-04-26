"""
Owner 8 — FastAPI Agent Orchestrator Service
Implements Agentic AI for LinkedIn simulation:
- Hiring Assistant (Supervisor Agent)
- Resume Parser Skill
- Job-Candidate Matching Skill
- Outreach Draft Generator
- Human-in-the-loop approval workflow
- WebSocket real-time progress streaming
"""

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from pydantic import BaseModel
import redis.asyncio as aioredis
import logging

from routers import tasks
from services.agent_orchestrator import AgentOrchestrator
from utils.auth import verify_token, verify_ws_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Globals ──────────────────────────────────────────────────
mongo_client: Optional[AsyncIOMotorClient] = None
redis_client = None
kafka_producer: Optional[AIOKafkaProducer] = None
orchestrator: Optional[AgentOrchestrator] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, redis_client, kafka_producer, orchestrator
    
    # MongoDB
    mongo_client = AsyncIOMotorClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    db = mongo_client.get_database("linkedin_nosql")
    
    # Redis
    redis_client = await aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    
    # Kafka producer
    kafka_brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
    kafka_producer = AIOKafkaProducer(bootstrap_servers=kafka_brokers)
    await kafka_producer.start()
    
    # Orchestrator
    orchestrator = AgentOrchestrator(db=db, redis=redis_client, kafka=kafka_producer)
    app.state.db = db
    app.state.redis = redis_client
    app.state.kafka = kafka_producer
    app.state.orchestrator = orchestrator
    
    # Start Kafka consumer in background
    asyncio.create_task(consume_ai_requests(db, redis_client, orchestrator))
    
    logger.info("[ai-service] Started")
    yield
    
    await kafka_producer.stop()
    await redis_client.close()
    mongo_client.close()

app = FastAPI(
    title="LinkedIn AI Agent Orchestrator",
    description="Agentic AI microservice for LinkedIn simulation — Hiring Assistant, Resume Parser, Job Matching",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(tasks.router, prefix="/ai/tasks", tags=["AI Tasks"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-service", "ts": datetime.utcnow().isoformat()}


# ── WebSocket endpoint ────────────────────────────────────────
active_connections: dict[str, list[WebSocket]] = {}

@app.websocket("/ws/ai/tasks/{task_id}")
async def websocket_task_progress(websocket: WebSocket, task_id: str, token: Optional[str] = None):
    if not await verify_ws_token(token):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    if task_id not in active_connections:
        active_connections[task_id] = []
    active_connections[task_id].append(websocket)
    
    try:
        # Send current state immediately
        db = app.state.db
        task = await db.agent_tasks.find_one({"task_id": task_id})
        if task:
            task["_id"] = str(task["_id"])
            if task.get("created_at"):
                task["created_at"] = task["created_at"].isoformat()
            if task.get("updated_at"):
                task["updated_at"] = task["updated_at"].isoformat()
            await websocket.send_json({"type": "task_state", "data": task})
        
        # Keep alive and wait for updates
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat", "ts": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        active_connections.get(task_id, []).remove(websocket)


async def broadcast_task_update(task_id: str, update: dict):
    """Broadcast task progress to all WebSocket subscribers."""
    connections = active_connections.get(task_id, [])
    dead = []
    for ws in connections:
        try:
            await ws.send_json(update)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections.remove(ws)

# Make broadcast available to orchestrator
app.state.broadcast = broadcast_task_update


async def consume_ai_requests(db, redis_client, orchestrator: AgentOrchestrator):
    """Kafka consumer loop for ai.requests topic."""
    brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
    consumer = AIOKafkaConsumer(
        "ai.requests",
        bootstrap_servers=brokers,
        group_id="ai-service-consumer",
        auto_offset_reset="earliest"
    )
    try:
        await consumer.start()
        logger.info("[ai-service] Kafka consumer started on ai.requests")
        async for msg in consumer:
            try:
                payload = json.loads(msg.value.decode())
                task_id = payload.get("task_id") or payload.get("payload", {}).get("task_id")
                if task_id:
                    task = await db.agent_tasks.find_one({"task_id": task_id}, {"status": 1})
                    if not task:
                        continue
                    if task.get("status") not in {"queued", "running"}:
                        continue

                    lock_key = f"ai:task:processing:{task_id}"
                    lock_acquired = await redis_client.set(lock_key, "1", ex=3600, nx=True)
                    if not lock_acquired:
                        continue

                    async def _run_locked(current_task_id: str):
                        try:
                            await orchestrator.run_task(current_task_id, broadcast_task_update)
                        finally:
                            await redis_client.delete(f"ai:task:processing:{current_task_id}")

                    asyncio.create_task(_run_locked(task_id))
            except Exception as e:
                logger.error(f"[ai-consumer] Error: {e}")
    except Exception as e:
        logger.error(f"[ai-consumer] Consumer failed: {e}")
    finally:
        await consumer.stop()
