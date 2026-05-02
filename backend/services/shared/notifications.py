from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from services.shared.document_store import insert_one as _ds_insert, find_many as _ds_find

_COLLECTION = 'notifications'


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
    _ds_insert(_COLLECTION, doc)
    return {**doc, 'notification_id': doc['_id']}


def list_notifications(member_id: str, page_size: int = 30) -> list[dict[str, Any]]:
    docs = _ds_find(_COLLECTION, {'member_id': member_id}, sort=[('created_at', -1)])
    docs = docs[:page_size]
    for d in docs:
        d['notification_id'] = d.get('notification_id') or d.pop('_id', None)
    return docs
