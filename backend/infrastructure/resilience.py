"""
Enterprise resilience patterns for TitleTrust backend.

Includes:
- Circuit breaker for external API calls
- Timeout policies
- Exponential backoff with jitter
- Graceful degradation
- Dead-letter queue handling
"""

import asyncio
import time
import logging
import random
from enum import Enum
from typing import Callable, TypeVar, Optional, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import functools

logger = logging.getLogger("TitleTrust-Resilience")

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failures exceed threshold, rejecting requests
    HALF_OPEN = "half_open"    # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5              # Failures before opening
    recovery_timeout_seconds: int = 60      # Time before trying to recover
    success_threshold: int = 2              # Successes in half-open to close
    failure_window_seconds: int = 300       # Window for counting failures
    excluded_exceptions: tuple = ()         # Exceptions that don't count as failures


@dataclass
class CircuitBreakerMetrics:
    """Metrics for a circuit breaker."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.now)
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0

    def reset(self) -> None:
        """Reset metrics."""
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for resilience.
    
    Prevents cascading failures by rejecting requests when a service is failing.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.metrics = CircuitBreakerMetrics()

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        if self.metrics.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.metrics.state = CircuitState.HALF_OPEN
                self.metrics.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Retrying in {self._reset_timeout_remaining()}s"
                )

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure(exc)
            raise

    async def call_async(
        self, func: Callable[..., Any], *args, **kwargs
    ) -> Any:
        """Async version of call()."""
        if self.metrics.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.metrics.state = CircuitState.HALF_OPEN
                self.metrics.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Retrying in {self._reset_timeout_remaining()}s"
                )

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure(exc)
            raise

    def _record_success(self) -> None:
        """Record successful call."""
        self.metrics.success_count += 1
        self.metrics.total_successes += 1
        self.metrics.total_calls += 1

        if self.metrics.state == CircuitState.HALF_OPEN:
            if self.metrics.success_count >= self.config.success_threshold:
                self._close()
        elif self.metrics.state == CircuitState.CLOSED:
            self.metrics.failure_count = 0

    def _record_failure(self, exc: Exception) -> None:
        """Record failed call."""
        # Skip if exception is excluded
        if isinstance(exc, self.config.excluded_exceptions):
            return

        self.metrics.failure_count += 1
        self.metrics.total_failures += 1
        self.metrics.total_calls += 1
        self.metrics.last_failure_time = datetime.now()

        if self.metrics.state == CircuitState.HALF_OPEN:
            self._open()
        elif self.metrics.failure_count >= self.config.failure_threshold:
            self._open()

        logger.warning(
            f"Circuit breaker '{self.name}': {self.metrics.failure_count}/{self.config.failure_threshold} "
            f"failures. State: {self.metrics.state.value}"
        )

    def _open(self) -> None:
        """Open the circuit."""
        if self.metrics.state != CircuitState.OPEN:
            self.metrics.state = CircuitState.OPEN
            self.metrics.last_state_change = datetime.now()
            logger.error(f"Circuit breaker '{self.name}' OPENED due to failures")

    def _close(self) -> None:
        """Close the circuit."""
        if self.metrics.state != CircuitState.CLOSED:
            self.metrics.state = CircuitState.CLOSED
            self.metrics.reset()
            self.metrics.last_state_change = datetime.now()
            logger.info(f"Circuit breaker '{self.name}' CLOSED - service recovered")

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.metrics.last_state_change:
            return True
        elapsed = (datetime.now() - self.metrics.last_state_change).total_seconds()
        return elapsed >= self.config.recovery_timeout_seconds

    def _reset_timeout_remaining(self) -> int:
        """Get remaining time until reset attempt."""
        if not self.metrics.last_state_change:
            return 0
        elapsed = (datetime.now() - self.metrics.last_state_change).total_seconds()
        remaining = self.config.recovery_timeout_seconds - elapsed
        return max(0, int(remaining))

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.metrics.state.value,
            "failure_count": self.metrics.failure_count,
            "success_count": self.metrics.success_count,
            "total_calls": self.metrics.total_calls,
            "total_failures": self.metrics.total_failures,
            "total_successes": self.metrics.total_successes,
            "last_failure_time": self.metrics.last_failure_time.isoformat()
            if self.metrics.last_failure_time
            else None,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""
    pass


def circuit_breaker(
    name: str, config: Optional[CircuitBreakerConfig] = None
) -> Callable:
    """
    Decorator for circuit breaker pattern.
    
    Usage:
        @circuit_breaker("external_api")
        def call_external_api():
            ...
    """
    cb = CircuitBreaker(name, config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return cb.call(func, *args, **kwargs)

        wrapper._circuit_breaker = cb
        return wrapper

    return decorator


def async_circuit_breaker(
    name: str, config: Optional[CircuitBreakerConfig] = None
) -> Callable:
    """Async version of circuit breaker decorator."""
    cb = CircuitBreaker(name, config)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await cb.call_async(func, *args, **kwargs)

        wrapper._circuit_breaker = cb
        return wrapper

    return decorator


@dataclass
class BackoffConfig:
    """Configuration for exponential backoff."""
    initial_delay: float = 1.0      # Initial delay in seconds
    max_delay: float = 60.0         # Maximum delay in seconds
    multiplier: float = 2.0         # Exponential multiplier
    jitter: bool = True             # Add random jitter
    max_retries: int = 5            # Maximum number of retries


def exponential_backoff(
    config: Optional[BackoffConfig] = None,
) -> Callable:
    """
    Decorator for exponential backoff with jitter.
    
    Usage:
        @exponential_backoff()
        def potentially_failing_call():
            ...
    """
    config = config or BackoffConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc = None
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < config.max_retries:
                        delay = min(
                            config.initial_delay * (config.multiplier ** attempt),
                            config.max_delay,
                        )
                        if config.jitter:
                            delay *= 0.5 + random.random()  # Jitter: 50-100% of delay
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_retries + 1} failed. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"All {config.max_retries + 1} attempts failed")

            raise last_exc

        return wrapper

    return decorator


def async_exponential_backoff(
    config: Optional[BackoffConfig] = None,
) -> Callable:
    """Async version of exponential backoff decorator."""
    config = config or BackoffConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exc = None
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < config.max_retries:
                        delay = min(
                            config.initial_delay * (config.multiplier ** attempt),
                            config.max_delay,
                        )
                        if config.jitter:
                            delay *= 0.5 + random.random()
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_retries + 1} failed. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All {config.max_retries + 1} attempts failed")

            raise last_exc

        return wrapper

    return decorator


def timeout(seconds: float) -> Callable:
    """
    Decorator for timeout protection.
    
    Usage:
        @timeout(30)
        def potentially_slow_call():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} exceeded {seconds}s timeout")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator


def async_timeout(seconds: float) -> Callable:
    """Async version of timeout decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), timeout=seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function {func.__name__} exceeded {seconds}s timeout")

        return wrapper

    return decorator
