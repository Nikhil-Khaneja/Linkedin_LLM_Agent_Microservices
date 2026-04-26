import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        trace_id = request.headers.get("x-trace-id", request_id)
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 2)

        response.headers["x-request-id"] = request_id
        response.headers["x-trace-id"] = trace_id
        response.headers["x-response-time-ms"] = str(duration_ms)
        return response