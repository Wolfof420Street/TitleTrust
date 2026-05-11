import time
import uuid
from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

import logging

try:
    from opentelemetry import trace
except ModuleNotFoundError:
    trace = None

logger = logging.getLogger("TitleTrust-Observability")
REQUEST_COUNT = Counter("titletrust_http_requests_total", "HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("titletrust_http_request_latency_ms", "Request latency in ms", ["method", "path"])
TRACER = trace.get_tracer("titletrust.api") if trace else None


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        start = time.perf_counter()
        if TRACER:
            with TRACER.start_as_current_span(request.url.path) as span:
                span.set_attribute("http.method", request.method)
                span.set_attribute("correlation_id", correlation_id)
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
        else:
            response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
        REQUEST_COUNT.labels(request.method, request.url.path, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, request.url.path).observe(elapsed_ms)
        logger.info(
            "request.completed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "latency_ms": elapsed_ms,
                "correlation_id": correlation_id,
            },
        )
        return response
