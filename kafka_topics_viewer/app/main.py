from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app import kafka_read

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Kafka Topics Viewer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "kafka_bootstrap": BOOTSTRAP}


@app.get("/api/topics")
async def api_topics_list():
    try:
        names = await asyncio.to_thread(kafka_read.list_topics, BOOTSTRAP)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Kafka unavailable: {exc}") from exc
    return {"topics": names, "bootstrap": BOOTSTRAP}


@app.get("/api/tail")
async def tail(
    topic: str = Query(..., min_length=1, max_length=249),
    limit: int = Query(100, ge=1, le=2000),
):
    try:
        rows = await asyncio.to_thread(kafka_read.tail_topic, BOOTSTRAP, topic, limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"topic": topic, "count": len(rows), "messages": rows}


@app.get("/api/tail-bulk")
async def tail_bulk(
    topics: str = Query(..., description="Comma-separated topic names"),
    limit_per_topic: int = Query(50, ge=1, le=500),
):
    names = [t.strip() for t in topics.split(",") if t.strip()]
    if not names:
        raise HTTPException(status_code=400, detail="No topics provided")
    if len(names) > 80:
        raise HTTPException(status_code=400, detail="Too many topics (max 80)")
    out: dict[str, list] = {}
    errors: dict[str, str] = {}
    for name in names:
        try:
            out[name] = await asyncio.to_thread(kafka_read.tail_topic, BOOTSTRAP, name, limit_per_topic)
        except Exception as exc:
            errors[name] = str(exc)
    merged: list[dict] = []
    for t, rows in out.items():
        for r in rows:
            merged.append({**r, "topic": t})
    merged.sort(
        key=lambda r: (
            r.get("timestamp_ms") or 0,
            r.get("topic") or "",
            r.get("partition") or 0,
            r.get("offset") or 0,
        )
    )
    return {"bootstrap": BOOTSTRAP, "by_topic": out, "merged": merged, "errors": errors}


@app.get("/")
def index():
    index_path = STATIC / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=500, detail="static/index.html missing")
    return FileResponse(index_path)
