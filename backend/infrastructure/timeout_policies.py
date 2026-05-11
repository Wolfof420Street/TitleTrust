"""
Timeout policies for different service types and operations.

This ensures consistent timeout behavior across the application and prevents
operations from hanging indefinitely.
"""

from dataclasses import dataclass
from typing import Dict, Optional

# HTTP/External API timeouts
HTTP_CONNECT_TIMEOUT = 10      # Initial connection
HTTP_READ_TIMEOUT = 30         # Reading response
HTTP_WRITE_TIMEOUT = 10        # Sending request
HTTP_TOTAL_TIMEOUT = 45        # Overall request

# GCP API timeouts
GCP_VISION_TIMEOUT = 60        # Vision API for image analysis
GCP_MAPS_TIMEOUT = 15          # Maps API for geolocation
GCP_TASKS_TIMEOUT = 10         # Cloud Tasks scheduling
GCP_FIRESTORE_TIMEOUT = 30     # Firestore operations

# Worker timeouts
WORKER_JOB_TIMEOUT = 600       # 10 minutes max for job processing
WORKER_HEARTBEAT_TIMEOUT = 5   # Heartbeat deadline
WORKER_QUEUE_POLL_TIMEOUT = 30 # Queue polling

# Agent timeouts
AGENT_STEP_TIMEOUT = 120       # Single agent step execution
AGENT_DECISION_TIMEOUT = 60    # Decision generation
AGENT_MEMORY_TIMEOUT = 10      # Memory operations

# Health check timeouts
HEALTH_CHECK_TIMEOUT = 5       # Health endpoint response
LIVENESS_TIMEOUT = 10          # Liveness probe timeout

# Firebase/Auth timeouts
FIREBASE_AUTH_TIMEOUT = 15     # Token verification
FIREBASE_MESSAGING_TIMEOUT = 30 # Push notification send

# Database timeouts
DB_TRANSACTION_TIMEOUT = 30    # Transaction deadline
DB_QUERY_TIMEOUT = 20          # Query execution

# File operation timeouts
FILE_UPLOAD_TIMEOUT = 120      # File upload deadline
FILE_PROCESSING_TIMEOUT = 300  # File processing (120 sec is typical, 300 is max)
FILE_CLEANUP_TIMEOUT = 30      # Cleanup operations


@dataclass
class ServiceTimeouts:
    """Timeout configuration for a service."""
    connect: float = HTTP_CONNECT_TIMEOUT
    read: float = HTTP_READ_TIMEOUT
    write: float = HTTP_WRITE_TIMEOUT
    total: float = HTTP_TOTAL_TIMEOUT


class TimeoutPolicies:
    """Central registry of timeout policies."""

    # Vision/Forensic service
    FORENSIC_ANALYSIS = 120     # Image analysis typically takes 30-60s, 120 is safe
    FORENSIC_UPLOAD = 60        # File upload

    # Geospatial service
    GEOSPATIAL_ANALYSIS = 45    # Location lookup + maps API
    GEOSPATIAL_VISION = 90      # Vision call for satellite images

    # Marathon (Agent) service
    MARATHON_STEP = 120         # Single step in agentic loop
    MARATHON_ITERATION = 180    # Full iteration (up to 3 steps)

    # Sync service
    SYNC_STATE_UPDATE = 10
    SYNC_NOTIFICATION = 15

    # Worker background jobs
    WORKER_JOB_PROCESSING = 600
    WORKER_CLEANUP = 60

    # API endpoints
    API_AUDIT_START = 60
    API_AUDIT_STATUS = 10
    API_AUDIT_RETRY = 30

    @staticmethod
    def get_timeout(operation: str) -> float:
        """Get timeout for an operation."""
        timeouts: Dict[str, float] = {
            "forensic_analysis": TimeoutPolicies.FORENSIC_ANALYSIS,
            "forensic_upload": TimeoutPolicies.FORENSIC_UPLOAD,
            "geospatial_analysis": TimeoutPolicies.GEOSPATIAL_ANALYSIS,
            "geospatial_vision": TimeoutPolicies.GEOSPATIAL_VISION,
            "marathon_step": TimeoutPolicies.MARATHON_STEP,
            "marathon_iteration": TimeoutPolicies.MARATHON_ITERATION,
            "sync_state": TimeoutPolicies.SYNC_STATE_UPDATE,
            "sync_notification": TimeoutPolicies.SYNC_NOTIFICATION,
            "worker_job": TimeoutPolicies.WORKER_JOB_PROCESSING,
            "worker_cleanup": TimeoutPolicies.WORKER_CLEANUP,
            "api_audit_start": TimeoutPolicies.API_AUDIT_START,
            "api_audit_status": TimeoutPolicies.API_AUDIT_STATUS,
            "api_audit_retry": TimeoutPolicies.API_AUDIT_RETRY,
        }
        return timeouts.get(operation, HTTP_TOTAL_TIMEOUT)

    @staticmethod
    def get_service_timeouts(service_name: str) -> Optional[ServiceTimeouts]:
        """Get timeout configuration for a service."""
        configs = {
            "vision": ServiceTimeouts(
                connect=10, read=60, write=10, total=GCP_VISION_TIMEOUT
            ),
            "maps": ServiceTimeouts(
                connect=5, read=15, write=5, total=GCP_MAPS_TIMEOUT
            ),
            "firestore": ServiceTimeouts(
                connect=10, read=30, write=10, total=GCP_FIRESTORE_TIMEOUT
            ),
            "messaging": ServiceTimeouts(
                connect=10, read=30, write=10, total=FIREBASE_MESSAGING_TIMEOUT
            ),
        }
        return configs.get(service_name)
