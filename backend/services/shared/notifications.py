from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import MongoClient

_CLIENT = None


def _mongo():
    global _CLIENT
    if _CLIENT is None:
        uri = os.environ.get('MONGO_URI') or os.environ.get('MONGO_URL') or 'mongodb://mongo:27017'
        _CLIENT = MongoClient(uri)
    db_name = os.environ.get('MONGO_DATABASE', 'linkedin_sim')
    return _CLIENT[db_name]


def notifications_collection():
    return _mongo()['notifications']


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
        '_id': f'ntf_{uuid4().hex[:12]}',
        'member_id': member_id,
        'type': notification_type,
        'title': title,
        'body': body,
        'actor_id': actor_id,
        'actor_name': actor_name,
        'target_url': target_url,
        'data': data or {},
        'is_read': False,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    notifications_collection().insert_one(doc)
    return {**doc, 'notification_id': doc['_id']}
