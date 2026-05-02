from __future__ import annotations

import fnmatch
import json
import os
import time
from collections import defaultdict
from typing import Any

CACHE_MODE = os.environ.get('CACHE_MODE', 'redis').lower()
_ALLOW_MEMORY = os.environ.get('APP_ENV') == 'test' or bool(os.environ.get('PYTEST_CURRENT_TEST'))
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
DEFAULT_TTL = int(os.environ.get('CACHE_DEFAULT_TTL_SECONDS', '120'))

_mem: dict[str, tuple[float | None, str]] = {}
_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
    'hits': 0,
    'misses': 0,
    'sets': 0,
    'deletes': 0,
    'increments': 0,
    'errors': 0,
    'namespaces': defaultdict(lambda: {'hits': 0, 'misses': 0, 'sets': 0, 'deletes': 0}),
})


def _service_name() -> str:
    try:
        from services.shared.common import service_name as _current_service_name
        return _current_service_name()
    except Exception:
        return os.environ.get('SERVICE_NAME', 'unknown-service')



def _namespace(key: str) -> str:
    return key.split(':', 1)[0] if ':' in key else key



def _purge_if_expired(key: str) -> None:
    item = _mem.get(key)
    if not item:
        return
    expires_at, _ = item
    if expires_at is not None and expires_at <= time.time():
        _mem.pop(key, None)



def _mem_get(key: str) -> str | None:
    _purge_if_expired(key)
    item = _mem.get(key)
    return None if not item else item[1]



def _mem_set(key: str, value: str, ttl: int | None = None) -> None:
    expires_at = None if ttl is None else time.time() + ttl
    _mem[key] = (expires_at, value)



def _mem_delete_pattern(pattern: str) -> int:
    deleted = 0
    for key in list(_mem.keys()):
        _purge_if_expired(key)
        if fnmatch.fnmatch(key, pattern):
            _mem.pop(key, None)
            deleted += 1
    return deleted



def _mem_incr(key: str, amount: int = 1, ttl: int | None = None) -> int:
    current = int(_mem_get(key) or '0') + amount
    _mem_set(key, str(current), ttl)
    return current



def _redis_client():
    from redis import Redis
    return Redis.from_url(REDIS_URL, decode_responses=True)



def _record(kind: str, key: str, amount: int = 1) -> None:
    service = _service_name()
    ns = _namespace(key)
    _stats[service][kind] += amount
    if kind in {'hits', 'misses', 'sets', 'deletes'}:
        _stats[service]['namespaces'][ns][kind] += amount



def is_redis_enabled() -> bool:
    if CACHE_MODE == 'memory' and not _ALLOW_MEMORY:
        raise RuntimeError('CACHE_MODE=memory is test-only. Use Redis in non-test environments.')
    if CACHE_MODE != 'redis':
        return False
    try:
        client = _redis_client()
        client.ping()
        return True
    except Exception:
        _record('errors', 'redis:ping')
        return False



def get_raw(key: str) -> str | None:
    value = None
    if is_redis_enabled():
        try:
            value = _redis_client().get(key)
        except Exception:
            _record('errors', key)
    if value is None and CACHE_MODE == 'memory':
        value = _mem_get(key)
    if value is None:
        _record('misses', key)
    else:
        _record('hits', key)
    return value



def set_raw(key: str, value: str, ttl: int | None = DEFAULT_TTL) -> None:
    if is_redis_enabled():
        try:
            client = _redis_client()
            if ttl is None:
                client.set(key, value)
            else:
                client.setex(key, ttl, value)
            _record('sets', key)
            return
        except Exception:
            _record('errors', key)
    if CACHE_MODE == 'memory':
        _mem_set(key, value, ttl)
        _record('sets', key)



def delete_pattern(pattern: str) -> int:
    deleted = 0
    if is_redis_enabled():
        try:
            client = _redis_client()
            keys = client.keys(pattern)
            deleted = client.delete(*keys) if keys else 0
            if deleted:
                _record('deletes', pattern, int(deleted))
            return deleted
        except Exception:
            _record('errors', pattern)
    if CACHE_MODE == 'memory':
        deleted = _mem_delete_pattern(pattern)
        if deleted:
            _record('deletes', pattern, int(deleted))
        return deleted
    return 0



def get_json(key: str) -> Any:
    raw = get_raw(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        _record('errors', key)
        return None



def set_json(key: str, value: Any, ttl: int | None = DEFAULT_TTL) -> None:
    set_raw(key, json.dumps(value, default=str, separators=(',', ':')), ttl)



def get_int(key: str) -> int | None:
    raw = get_raw(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        _record('errors', key)
        return None



def set_int(key: str, value: int, ttl: int | None = DEFAULT_TTL) -> None:
    set_raw(key, str(value), ttl)



def incr(key: str, amount: int = 1, ttl: int | None = None) -> int:
    if is_redis_enabled():
        try:
            client = _redis_client()
            value = client.incrby(key, amount)
            if ttl:
                client.expire(key, ttl)
            _stats[_service_name()]['increments'] += amount
            return int(value)
        except Exception:
            _record('errors', key)
    if CACHE_MODE == 'memory':
        value = _mem_incr(key, amount, ttl)
        _stats[_service_name()]['increments'] += amount
        return value
    raise RuntimeError('Redis unavailable for incr and memory fallback disabled outside tests')



def delete_key(key: str) -> int:
    if is_redis_enabled():
        try:
            deleted = int(_redis_client().delete(key))
            if deleted:
                _record('deletes', key, deleted)
            return deleted
        except Exception:
            _record('errors', key)
    if CACHE_MODE == 'memory':
        deleted = _mem_delete_pattern(key)
        if deleted:
            _record('deletes', key, deleted)
        return deleted
    return 0



def get_cache_stats() -> dict[str, Any]:
    service = _service_name()
    current = _stats[service]
    lookups = current['hits'] + current['misses']
    hit_rate = round((current['hits'] / lookups) * 100, 2) if lookups else 0.0
    namespaces = {}
    for ns, values in current['namespaces'].items():
        ns_lookups = values['hits'] + values['misses']
        namespaces[ns] = {
            **values,
            'hit_rate_pct': round((values['hits'] / ns_lookups) * 100, 2) if ns_lookups else 0.0,
        }
    return {
        'service': service,
        'mode': CACHE_MODE,
        'lookups': lookups,
        'hits': current['hits'],
        'misses': current['misses'],
        'sets': current['sets'],
        'deletes': current['deletes'],
        'increments': current['increments'],
        'errors': current['errors'],
        'hit_rate_pct': hit_rate,
        'namespaces': namespaces,
    }



def reset_memory_cache() -> None:
    _mem.clear()
    _stats.clear()
