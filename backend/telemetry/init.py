import os
import logging
from typing import Optional

from fastapi import FastAPI

try:
    from opentelemetry import trace, metrics
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
except ImportError:
    # Gracefully degrade if OpenTelemetry is not installed
    trace = None
    metrics = None
    TracerProvider = None
    FastAPIInstrumentor = None
    RequestsInstrumentor = None

logger = logging.getLogger("TitleTrust-Telemetry")


def init_tracing(
    app: FastAPI,
    service_name: str = "titletrust-backend",
    service_namespace: str = "titletrust",
    environment: str = "development",
) -> Optional[TracerProvider]:
    """
    Initialize OpenTelemetry tracing with OTLP exporter.
    
    Args:
        service_name: The name of the service
        service_namespace: The namespace of the service
        environment: The deployment environment (development, staging, production)
    
    Returns:
        TracerProvider instance or None if tracing is not available
    """
    if not trace or not TracerProvider:
        logger.warning("OpenTelemetry not fully installed. Tracing disabled.")
        return None

    try:
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.namespace": service_namespace,
                "deployment.environment": environment,
            }
        )
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            span_processor = BatchSpanProcessor(trace_exporter)
            logger.info(f"Configured OTLP trace exporter for {otlp_endpoint}")
        else:
            logger.warning("Tracing exporter not configured. Set OTEL_EXPORTER_OTLP_ENDPOINT.")
            return None

        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(trace_provider)

        if FastAPIInstrumentor:
            FastAPIInstrumentor.instrument_app(app)
            logger.debug("Instrumented FastAPI")

        if RequestsInstrumentor:
            RequestsInstrumentor().instrument()
            logger.debug("Instrumented requests library")

        logger.info("OpenTelemetry tracing initialized successfully")
        return trace_provider

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry tracing: {e}")
        return None


def init_metrics(
    service_name: str = "titletrust-backend",
) -> Optional[MeterProvider]:
    """
    Initialize OpenTelemetry metrics.
    
    Args:
        service_name: The name of the service
    
    Returns:
        MeterProvider instance or None if metrics are not available
    """
    if not metrics or not MeterProvider:
        logger.warning("OpenTelemetry metrics not available")
        return None

    try:
        readers = []
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otlp_endpoint)))
        meter_provider = MeterProvider(metric_readers=readers)
        
        # Set global meter provider
        metrics.set_meter_provider(meter_provider)
        
        logger.info("OpenTelemetry metrics initialized successfully")
        return meter_provider

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry metrics: {e}")
        return None


def initialize_telemetry(
    app: FastAPI,
    service_name: str = "titletrust-backend",
    service_namespace: str = "titletrust",
    environment: str = "development",
) -> dict:
    """
    Initialize all telemetry components.
    
    Returns:
        Dictionary with initialized providers or empty dict if disabled
    """
    result = {
        "tracing_enabled": False,
        "metrics_enabled": False,
        "trace_provider": None,
        "meter_provider": None,
    }

    # Initialize tracing
    trace_provider = init_tracing(app, service_name, service_namespace, environment)
    if trace_provider:
        result["tracing_enabled"] = True
        result["trace_provider"] = trace_provider

    # Initialize metrics
    meter_provider = init_metrics(service_name)
    if meter_provider:
        result["metrics_enabled"] = True
        result["meter_provider"] = meter_provider

    logger.info(
        f"Telemetry initialization complete. "
        f"Tracing: {result['tracing_enabled']}, Metrics: {result['metrics_enabled']}"
    )

    return result
