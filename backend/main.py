import logging
import os
import sys

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api import audit_router, auth_router, health_router
from config import get_settings
from logging_config import configure_logging
from backend.middleware.adaptive_protection import AdaptiveProtectionMiddleware
from middleware.observability import CorrelationMiddleware
from middleware.rate_limit import enforce_rate_limit
from backend.security.abuse_detection import AbuseDetectionEngine
from backend.security.anomaly_detection import AnomalyDetectionEngine

configure_logging()
logger = logging.getLogger("TitleTrust-Backend")
settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app = FastAPI(title="TitleTrust API", version="3.0.0")

abuse_engine = AbuseDetectionEngine(AnomalyDetectionEngine(None))

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Correlation-ID"],
)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(AdaptiveProtectionMiddleware, abuse_engine=abuse_engine)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(audit_router.router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(auth_router.router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(health_router.router)

logger.info("TitleTrust backend started")
