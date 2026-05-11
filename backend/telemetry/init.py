"""
OpenTelemetry initialization for TitleTrust backend.
Configures tracing, metrics, and logging exporters.
"""

import os
import logging
from typing import Optional

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.exporter.gcp_trace import CloudTraceExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import SimpleMetricReader
    from opentelemetry.exporter.gcp_trace import CloudTraceExporter as MetricsExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
except ImportError:
    # Gracefully degrade if OpenTelemetry is not installed
    trace = None
    metrics = None
    TracerProvider = None
    CloudTraceExporter = None
    FastAPIInstrumentor = None
    RequestsInstrumentor = None

logger = logging.getLogger("TitleTrust-Telemetry")


def init_tracing(
    service_name: str = "titletrust-backend",
    service_namespace: str = "titletrust",
    environment: str = "development",
) -> Optional[TracerProvider]:
    """
    Initialize OpenTelemetry tracing with GCP Cloud Trace exporter.
    
    Args:
        service_name: The name of the service
        service_namespace: The namespace of the service
        environment: The deployment environment (development, staging, production)
    
    Returns:
        TracerProvider instance or None if tracing is not available
    """
    if not trace or not CloudTraceExporter:
        logger.warning("OpenTelemetry not fully installed. Tracing disabled.")
        return None

    try:
        gcp_project_id = os.environ.get("GCP_PROJECT_ID")
        
        # Create trace exporter
        if gcp_project_id:
            trace_exporter = CloudTraceExporter(project_id=gcp_project_id)
            logger.info(f"Configured GCP Cloud Trace exporter for project {gcp_project_id}")
        else:
            logger.warning("GCP_PROJECT_ID not set. Tracing disabled.")
            return None

        # Create tracer provider
        trace_provider = TracerProvider()
        trace_provider.add_span_processor(SimpleSpanProcessor(trace_exporter))
        
        # Set global tracer provider
        trace.set_tracer_provider(trace_provider)
        
        # Instrument popular libraries
        if FastAPIInstrumentor:
            FastAPIInstrumentor().instrument()
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
        meter_provider = MeterProvider()
        
        # Set global meter provider
        metrics.set_meter_provider(meter_provider)
        
        logger.info("OpenTelemetry metrics initialized successfully")
        return meter_provider

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry metrics: {e}")
        return None


def initialize_telemetry(
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
    trace_provider = init_tracing(service_name, service_namespace, environment)
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
