import time
from collections import defaultdict
from threading import Lock

from app.core.exceptions import RateLimitExceededException


class InMemoryRateLimiter:
    """Thread-safe sliding window rate limiter for authentication endpoints."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check_rate_limit(self, key: str, max_attempts: int, window_seconds: int) -> None:
        """Check whether the request key has exceeded maximum attempts within window.

        Raises:
            RateLimitExceededException: If rate limit threshold is breached.
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            # Purge entries older than the window
            timestamps = [t for t in self._requests[key] if t > cutoff]
            if len(timestamps) >= max_attempts:
                raise RateLimitExceededException()

            timestamps.append(now)
            self._requests[key] = timestamps

    def is_allowed(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """Check if request is within rate limit; records timestamp if allowed."""
        try:
            self.check_rate_limit(key, max_attempts, window_seconds)
            return True
        except RateLimitExceededException:
            return False

    def reset(self, key: str) -> None:
        """Clear rate limit entries for a specific key (e.g. after successful login)."""
        with self._lock:
            self._requests.pop(key, None)

    def clear_all(self) -> None:
        """Clear all rate limit entries (for test tear-down)."""
        with self._lock:
            self._requests.clear()


rate_limiter = InMemoryRateLimiter()
