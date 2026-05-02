from __future__ import annotations

import copy
import os
from collections import defaultdict
from typing import Any

_DOC_MODE = os.environ.get("DOC_STORE_MODE", "mongo").lower()
_ALLOW_MEMORY = os.environ.get('APP_ENV') == 'test' or bool(os.environ.get('PYTEST_CURRENT_TEST'))
_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://mongo:27017")
_MONGO_DB = os.environ.get("MONGO_DATABASE", "linkedin_sim_docs")

_mem_store: dict[str, list[dict[str, Any]]] = defaultdict(list)


def is_memory() -> bool:
    if _DOC_MODE == 'memory' and not _ALLOW_MEMORY:
        raise RuntimeError('DOC_STORE_MODE=memory is test-only. Use MongoDB in non-test environments.')
    return _DOC_MODE == "memory"


def _client():
    from pymongo import MongoClient
    return MongoClient(_MONGO_URL)


def reset_memory_store() -> None:
    _mem_store.clear()


def _match(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, value in query.items():
        if doc.get(key) != value:
            return False
    return True


def find_one(collection: str, query: dict[str, Any]) -> dict[str, Any] | None:
    if is_memory():
        for doc in _mem_store[collection]:
            if _match(doc, query):
                return copy.deepcopy(doc)
        return None
    client = _client()
    try:
        doc = client[_MONGO_DB][collection].find_one(query, {"_id": 0})
        return copy.deepcopy(doc) if doc else None
    finally:
        client.close()


def find_many(collection: str, query: dict[str, Any] | None = None, sort: list[tuple[str, int]] | None = None) -> list[dict[str, Any]]:
    query = query or {}
    if is_memory():
        items = [copy.deepcopy(doc) for doc in _mem_store[collection] if _match(doc, query)]
        if sort:
            for key, direction in reversed(sort):
                items.sort(key=lambda item: item.get(key), reverse=direction < 0)
        return items
    client = _client()
    try:
        cursor = client[_MONGO_DB][collection].find(query, {"_id": 0})
        if sort:
            cursor = cursor.sort(sort)
        return [copy.deepcopy(item) for item in cursor]
    finally:
        client.close()


def insert_one(collection: str, document: dict[str, Any]) -> None:
    if is_memory():
        _mem_store[collection].append(copy.deepcopy(document))
        return
    client = _client()
    try:
        client[_MONGO_DB][collection].insert_one(copy.deepcopy(document))
    finally:
        client.close()


def replace_one(collection: str, query: dict[str, Any], document: dict[str, Any], upsert: bool = False) -> None:
    if is_memory():
        for idx, doc in enumerate(_mem_store[collection]):
            if _match(doc, query):
                _mem_store[collection][idx] = copy.deepcopy(document)
                return
        if upsert:
            _mem_store[collection].append(copy.deepcopy(document))
        return
    client = _client()
    try:
        client[_MONGO_DB][collection].replace_one(query, copy.deepcopy(document), upsert=upsert)
    finally:
        client.close()


def update_one(collection: str, query: dict[str, Any], updates: dict[str, Any], upsert: bool = False) -> bool:
    if is_memory():
        for idx, doc in enumerate(_mem_store[collection]):
            if _match(doc, query):
                updated = copy.deepcopy(doc)
                updated.update(copy.deepcopy(updates))
                _mem_store[collection][idx] = updated
                return True
        if upsert:
            created = copy.deepcopy(query)
            created.update(copy.deepcopy(updates))
            _mem_store[collection].append(created)
            return True
        return False
    client = _client()
    try:
        result = client[_MONGO_DB][collection].update_one(query, {"$set": copy.deepcopy(updates)}, upsert=upsert)
        return bool(result.matched_count or result.upserted_id)
    finally:
        client.close()


def delete_many(collection: str, query: dict[str, Any]) -> int:
    if is_memory():
        before = len(_mem_store[collection])
        _mem_store[collection] = [doc for doc in _mem_store[collection] if not _match(doc, query)]
        return before - len(_mem_store[collection])
    client = _client()
    try:
        result = client[_MONGO_DB][collection].delete_many(query)
        return int(result.deleted_count)
    finally:
        client.close()
