from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import MongoClient

_COLLECTION = "notifications"
_client: MongoClient | None = None
_client_lock = threading.Lock()


def _notifications_collection():
    """Same DB/collection as member_profile_service list_notifications (linkedin_sim.notifications)."""
    global _client
    with _client_lock:
        if _client is None:
            uri = os.environ.get("MONGO_URI") or os.environ.get("MONGO_URL") or "mongodb://mongo:27017"
            _client = MongoClient(uri)
        db_name = os.environ.get("MONGO_DATABASE", "linkedin_sim")
        return _client[db_name][_COLLECTION]


def create_notification(
    member_id: str,
    notification_type: str,
    title: str,
    body: str,
    *,
    actor_id: str | None = None,
    actor_name: str | None = None,
    target_url: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = {
        "_id": f"ntf_{uuid4().hex[:12]}",
        "member_id": member_id,
        "type": notification_type,
        "title": title,
        "body": body,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "target_url": target_url,
        "data": data or {},
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _notifications_collection().insert_one(doc)
    return {**doc, "notification_id": doc["_id"]}


def list_notifications(member_id: str, page_size: int = 30) -> list[dict[str, Any]]:
    cur = (
        _notifications_collection()
        .find({"member_id": member_id})
        .sort("created_at", -1)
        .limit(int(page_size))
    )
    docs = list(cur)
    for d in docs:
        d["notification_id"] = d.get("notification_id") or d.pop("_id", None)
    return docs
