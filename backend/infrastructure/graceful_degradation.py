"""
Graceful degradation patterns for when external services fail.

Allows the system to continue operating with reduced functionality
rather than failing completely.
"""

import logging
from enum import Enum
from typing import Optional, Any, Dict, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("TitleTrust-GracefulDegradation")


class DegradationLevel(str, Enum):
    """Service degradation levels."""
    NORMAL = "normal"              # Full functionality
    DEGRADED = "degraded"          # Reduced functionality
    UNAVAILABLE = "unavailable"    # Service down, offline mode


@dataclass
class DegradedResponse:
    """Response when service operates in degraded mode."""
    data: Optional[Any]
    is_degraded: bool
    degradation_level: DegradationLevel
    message: str
    cached_at: Optional[datetime] = None
    cache_duration_seconds: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data": self.data,
            "is_degraded": self.is_degraded,
            "degradation_level": self.degradation_level.value,
            "message": self.message,
            "cached_at": self.cached_at.isoformat() if self.cached_at else None,
            "cache_duration_seconds": self.cache_duration_seconds,
        }


class GracefulDegradationManager:
    """
    Manages graceful degradation when external services fail.

    Provides fallback strategies and caching for resilience.
    """

    def __init__(self):
        self.service_status: Dict[str, DegradationLevel] = {}
        self.fallback_caches: Dict[str, Dict[str, Any]] = {}

    def mark_service_degraded(
        self, service_name: str, level: DegradationLevel, reason: str = ""
    ) -> None:
        """Mark a service as degraded."""
        old_level = self.service_status.get(service_name, DegradationLevel.NORMAL)
        self.service_status[service_name] = level

        if old_level != level:
            logger.warning(
                f"Service '{service_name}' degraded: {old_level.value} -> {level.value}. "
                f"Reason: {reason}"
            )

    def get_service_level(self, service_name: str) -> DegradationLevel:
        """Get current degradation level for a service."""
        return self.service_status.get(service_name, DegradationLevel.NORMAL)

    def is_service_available(self, service_name: str) -> bool:
        """Check if service is available."""
        level = self.get_service_level(service_name)
        return level != DegradationLevel.UNAVAILABLE

    def cache_fallback(
        self, service_name: str, key: str, data: Any, ttl_seconds: int = 3600
    ) -> None:
        """Cache data for fallback use."""
        if service_name not in self.fallback_caches:
            self.fallback_caches[service_name] = {}

        self.fallback_caches[service_name][key] = {
            "data": data,
            "cached_at": datetime.now(),
            "ttl_seconds": ttl_seconds,
        }

        logger.debug(f"Cached fallback data for {service_name}/{key} (TTL: {ttl_seconds}s)")

    def get_fallback_data(self, service_name: str, key: str) -> Optional[Any]:
        """Retrieve cached fallback data."""
        if service_name not in self.fallback_caches:
            return None

        cached = self.fallback_caches[service_name].get(key)
        if not cached:
            return None

        # Check TTL
        age = (datetime.now() - cached["cached_at"]).total_seconds()
        if age > cached["ttl_seconds"]:
            del self.fallback_caches[service_name][key]
            logger.debug(f"Fallback data for {service_name}/{key} expired")
            return None

        logger.info(f"Using cached fallback data for {service_name}/{key} (age: {age:.1f}s)")
        return cached["data"]

    @staticmethod
    def get_degraded_response(
        service_name: str,
        level: DegradationLevel,
        fallback_data: Optional[Any] = None,
        message: str = "",
    ) -> DegradedResponse:
        """Create a degraded response."""
        if not message:
            if level == DegradationLevel.DEGRADED:
                message = f"{service_name} is operating in degraded mode"
            else:
                message = f"{service_name} is unavailable, using cached data"

        return DegradedResponse(
            data=fallback_data,
            is_degraded=True,
            degradation_level=level,
            message=message,
            cached_at=datetime.now() if fallback_data else None,
        )


# Global degradation manager instance
_degradation_manager = GracefulDegradationManager()


def get_degradation_manager() -> GracefulDegradationManager:
    """Get the global degradation manager."""
    return _degradation_manager


class DegradableService:
    """Base class for services that support graceful degradation."""

    def __init__(self, name: str, fallback_fn: Optional[Callable] = None):
        self.name = name
        self.fallback_fn = fallback_fn
        self.manager = get_degradation_manager()

    def execute(
        self, fn: Callable, *args, cache_key: Optional[str] = None, **kwargs
    ) -> Any:
        """
        Execute a service function with graceful degradation.

        Args:
            fn: Function to execute
            args: Positional arguments
            cache_key: Key for caching fallback data
            kwargs: Keyword arguments

        Returns:
            Result or degraded response
        """
        try:
            result = fn(*args, **kwargs)

            # Cache successful result for fallback
            if cache_key:
                self.manager.cache_fallback(self.name, cache_key, result)

            return result

        except Exception as exc:
            logger.error(f"Service '{self.name}' error: {exc}")

            # Try to use fallback
            fallback_data = None
            if cache_key:
                fallback_data = self.manager.get_fallback_data(self.name, cache_key)

            if fallback_data:
                self.manager.mark_service_degraded(
                    self.name,
                    DegradationLevel.DEGRADED,
                    reason=str(exc),
                )
                return DegradedResponse(
                    data=fallback_data,
                    is_degraded=True,
                    degradation_level=DegradationLevel.DEGRADED,
                    message=f"{self.name} is degraded, using cached data",
                    cached_at=datetime.now(),
                )
            else:
                self.manager.mark_service_degraded(
                    self.name,
                    DegradationLevel.UNAVAILABLE,
                    reason=str(exc),
                )

                # Use fallback function if provided
                if self.fallback_fn:
                    try:
                        fallback_result = self.fallback_fn(*args, **kwargs)
                        return DegradedResponse(
                            data=fallback_result,
                            is_degraded=True,
                            degradation_level=DegradationLevel.UNAVAILABLE,
                            message=f"{self.name} unavailable, using fallback implementation",
                        )
                    except Exception as fallback_exc:
                        logger.error(f"Fallback for '{self.name}' also failed: {fallback_exc}")

                return DegradedResponse(
                    data=None,
                    is_degraded=True,
                    degradation_level=DegradationLevel.UNAVAILABLE,
                    message=f"{self.name} is unavailable and no fallback available",
                )

    async def execute_async(
        self, fn: Callable, *args, cache_key: Optional[str] = None, **kwargs
    ) -> Any:
        """Async version of execute()."""
        try:
            result = await fn(*args, **kwargs)

            if cache_key:
                self.manager.cache_fallback(self.name, cache_key, result)

            return result

        except Exception as exc:
            logger.error(f"Service '{self.name}' error: {exc}")

            fallback_data = None
            if cache_key:
                fallback_data = self.manager.get_fallback_data(self.name, cache_key)

            if fallback_data:
                self.manager.mark_service_degraded(
                    self.name,
                    DegradationLevel.DEGRADED,
                    reason=str(exc),
                )
                return DegradedResponse(
                    data=fallback_data,
                    is_degraded=True,
                    degradation_level=DegradationLevel.DEGRADED,
                    message=f"{self.name} is degraded, using cached data",
                    cached_at=datetime.now(),
                )
            else:
                self.manager.mark_service_degraded(
                    self.name,
                    DegradationLevel.UNAVAILABLE,
                    reason=str(exc),
                )

                if self.fallback_fn:
                    try:
                        fallback_result = await self.fallback_fn(*args, **kwargs) \
                            if hasattr(self.fallback_fn, '__await__') \
                            else self.fallback_fn(*args, **kwargs)
                        return DegradedResponse(
                            data=fallback_result,
                            is_degraded=True,
                            degradation_level=DegradationLevel.UNAVAILABLE,
                            message=f"{self.name} unavailable, using fallback implementation",
                        )
                    except Exception as fallback_exc:
                        logger.error(f"Fallback for '{self.name}' also failed: {fallback_exc}")

                return DegradedResponse(
                    data=None,
                    is_degraded=True,
                    degradation_level=DegradationLevel.UNAVAILABLE,
                    message=f"{self.name} is unavailable and no fallback available",
                )

    def get_status(self) -> Dict[str, Any]:
        """Get service degradation status."""
        return {
            "service": self.name,
            "level": self.manager.get_service_level(self.name).value,
            "available": self.manager.is_service_available(self.name),
        }
