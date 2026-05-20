import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api import audit_router, auth_router, health_router, upload_router
from backend.api.realtime_router import router as realtime_router
from backend.config import get_settings
from backend.logging_config import configure_logging
from backend.middleware.adaptive_protection import AdaptiveProtectionMiddleware
from backend.middleware.observability import CorrelationMiddleware
from backend.middleware.rate_limit import enforce_rate_limit
from backend.auth import get_current_user
from backend.middleware.security_headers import AdvancedSecurityHeadersMiddleware
from backend.security.abuse_detection import AbuseDetectionEngine
from backend.security.anomaly_detection import AnomalyDetectionEngine
from backend.services.firebase import db
from backend.telemetry.init import initialize_telemetry
from backend.realtime.broadcaster import broadcaster

configure_logging()
logger = logging.getLogger("TitleTrust-Backend")
settings = get_settings()


app = FastAPI(title="TitleTrust API", version="3.0.0")

abuse_engine = AbuseDetectionEngine(AnomalyDetectionEngine(db))

app.add_middleware(AdvancedSecurityHeadersMiddleware)
app.add_middleware(AdaptiveProtectionMiddleware, abuse_engine=abuse_engine)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-Correlation-ID",
        "X-Request-Signature",
        "X-Request-Timestamp",
        "X-Device-Session-ID",
        "X-Request-Signed",
    ],
)


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
app.include_router(upload_router.router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(health_router.router)
app.include_router(realtime_router, dependencies=[Depends(enforce_rate_limit), Depends(get_current_user)])

initialize_telemetry(app=app, environment=settings.ENV)

logger.info("TitleTrust backend started")


@app.on_event("startup")
async def _realtime_startup():
    try:
        await broadcaster.start()
        logger.info("Realtime broadcaster started")
    except Exception as e:
        logger.exception("Failed to start realtime broadcaster: %s", e)


@app.on_event("shutdown")
async def _realtime_shutdown():
    try:
        await broadcaster.stop()
        logger.info("Realtime broadcaster stopped")
    except Exception as e:
        logger.exception("Failed to stop realtime broadcaster: %s", e)
