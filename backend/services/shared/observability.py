from __future__ import annotations

import json
import logging
import os
import time
from typing import Callable, Any

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from services.shared.cache import get_cache_stats
from services.shared.common import clear_trace, service_name, set_trace, trace_id

_REQUESTS_TOTAL = Counter(
    'linkedin_service_http_requests_total',
    'Total HTTP requests handled by service',
    ['service', 'method', 'path', 'status'],
)
_REQUEST_LATENCY = Histogram(
    'linkedin_service_http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['service', 'method', 'path'],
)
_CACHE_HIT_RATE = Gauge(
    'linkedin_service_cache_hit_rate_percent',
    'Current cache hit rate percentage',
    ['service'],
)
_CACHE_LOOKUPS = Gauge(
    'linkedin_service_cache_lookups_total',
    'Current cache lookups observed by service',
    ['service'],
)
_SERVICE_INFO = Gauge(
    'linkedin_service_build_info',
    'Static service info',
    ['service', 'environment', 'version'],
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts': self.formatTime(record, datefmt='%Y-%m-%dT%H:%M:%S'),
            'level': record.levelname,
            'service': getattr(record, 'service', service_name()),
            'trace_id': getattr(record, 'trace_id', trace_id()),
            'message': record.getMessage(),
        }
        for field in ('method', 'path', 'status_code', 'duration_ms', 'client_host'):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        context = getattr(record, 'context', None)
        if isinstance(context, dict):
            for key, value in context.items():
                if value is not None:
                    payload[key] = value
        return json.dumps(payload, separators=(',', ':'), default=str)


def log_event(logger: logging.Logger, message: str, *, level: int = logging.INFO, **context: Any) -> None:
    logger.log(
        level,
        message,
        extra={
            'service': context.pop('service', service_name()),
            'trace_id': context.pop('trace_id', trace_id()),
            'context': context,
        },
    )


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())
    logger.propagate = False
    return logger



def attach_observability(app: FastAPI, svc_name: str) -> None:
    service_name(svc_name)
    logger = get_logger(svc_name)
    _SERVICE_INFO.labels(service=svc_name, environment=os.environ.get('APP_ENV', 'dev'), version=os.environ.get('APP_VERSION', '0.1.0')).set(1)

    @app.middleware('http')
    async def trace_and_metrics_middleware(request: Request, call_next: Callable):
        service_name(svc_name)
        trc = set_trace(request.headers.get('X-Trace-Id'))
        request.state.trace_id = trc
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers['X-Trace-Id'] = trc
            return response
        finally:
            elapsed = time.perf_counter() - start
            _REQUESTS_TOTAL.labels(service=svc_name, method=request.method, path=request.url.path, status=str(status_code)).inc()
            _REQUEST_LATENCY.labels(service=svc_name, method=request.method, path=request.url.path).observe(elapsed)
            cache_stats = get_cache_stats()
            _CACHE_HIT_RATE.labels(service=svc_name).set(cache_stats['hit_rate_pct'])
            _CACHE_LOOKUPS.labels(service=svc_name).set(cache_stats['lookups'])
            logger.info(
                'request_complete',
                extra={
                    'service': svc_name,
                    'trace_id': trc,
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': status_code,
                    'duration_ms': round(elapsed * 1000, 2),
                    'client_host': request.client.host if request.client else None,
                },
            )
            clear_trace()

    @app.get('/ops/healthz', tags=['ops'])
    async def ops_healthz():
        service_name(svc_name)
        return {'status': 'ok', 'service': svc_name}

    @app.get('/ops/cache-stats', tags=['ops'])
    async def ops_cache_stats():
        service_name(svc_name)
        return get_cache_stats()

    @app.get('/ops/metrics', tags=['ops'])
    async def ops_metrics():
        service_name(svc_name)
        return PlainTextResponse(generate_latest().decode('utf-8'), media_type=CONTENT_TYPE_LATEST)
