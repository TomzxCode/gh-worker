"""Retry utilities for handling transient failures."""

import asyncio
import functools
import subprocess
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, message: str, last_exception: Exception):
        """Initialize retry error.

        Args:
            message: Error message
            last_exception: The last exception that was raised
        """
        super().__init__(message)
        self.last_exception = last_exception


def is_transient_error(exception: Exception) -> bool:
    """Check if an exception is transient and can be retried.

    Args:
        exception: The exception to check

    Returns:
        True if the error is transient, False otherwise
    """
    # Network and subprocess errors are often transient
    if isinstance(exception, (subprocess.TimeoutExpired, ConnectionError, OSError)):
        return True

    # Check for specific error messages
    error_str = str(exception).lower()
    transient_indicators = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "rate limit",
        "too many requests",
        "503",
        "502",
        "504",
    ]

    return any(indicator in error_str for indicator in transient_indicators)


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    transient_only: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry a function on failure with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Factor to multiply delay by after each retry
        max_delay: Maximum delay in seconds between retries
        transient_only: Only retry on transient errors (default: True)

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            delay = initial_delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if transient_only and not is_transient_error(e):
                        logger.error(
                            "non_transient_error_not_retrying",
                            function=func.__name__,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        raise

                    # Check if we're out of attempts
                    if attempt == max_attempts:
                        logger.error(
                            "max_retry_attempts_reached",
                            function=func.__name__,
                            attempts=attempt,
                            error=str(e),
                        )
                        break

                    # Log and wait before retry
                    logger.warning(
                        "retrying_after_error",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=delay,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                    import time

                    time.sleep(delay)

                    # Exponential backoff
                    delay = min(delay * backoff_factor, max_delay)

            # All retries exhausted
            if last_exception:
                raise RetryError(
                    f"Failed after {max_attempts} attempts: {last_exception}",
                    last_exception,
                )

            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    transient_only: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Async version of retry decorator.

    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Factor to multiply delay by after each retry
        max_delay: Maximum delay in seconds between retries
        transient_only: Only retry on transient errors (default: True)

    Returns:
        Decorated async function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            delay = initial_delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if transient_only and not is_transient_error(e):
                        logger.error(
                            "non_transient_error_not_retrying",
                            function=func.__name__,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        raise

                    # Check if we're out of attempts
                    if attempt == max_attempts:
                        logger.error(
                            "max_retry_attempts_reached",
                            function=func.__name__,
                            attempts=attempt,
                            error=str(e),
                        )
                        break

                    # Log and wait before retry
                    logger.warning(
                        "retrying_after_error",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=delay,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                    await asyncio.sleep(delay)

                    # Exponential backoff
                    delay = min(delay * backoff_factor, max_delay)

            # All retries exhausted
            if last_exception:
                raise RetryError(
                    f"Failed after {max_attempts} attempts: {last_exception}",
                    last_exception,
                )

            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator
