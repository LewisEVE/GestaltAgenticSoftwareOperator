"""Retry policies for Gestalt runtime services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


async def with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    min_wait_seconds: float = 0.5,
    max_wait_seconds: float = 4.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Execute an async operation with exponential backoff retries."""

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(min=min_wait_seconds, max=max_wait_seconds),
            retry=retry_if_exception_type(retry_on),
            reraise=True,
        ):
            with attempt:
                return await operation()
    except RetryError as exc:  # pragma: no cover - tenacity reraises by default
        last_error = exc.last_attempt.exception()
        if last_error is None:
            raise RuntimeError("Retry operation failed without a captured exception.") from exc
        raise RuntimeError("Retry operation failed after exhausting retries.") from last_error

    msg = "retry operation exited without result"
    raise RuntimeError(msg)
