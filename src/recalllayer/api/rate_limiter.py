"""Simple sliding-window rate limiter for per-key request throttling.

No external dependencies — uses only the standard library.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock


class SlidingWindowRateLimiter:
    """Limit requests to *max_requests* per *window_seconds* per identifier.

    Thread-safe via a per-key lock.  Identifiers are typically API keys or
    remote IP addresses (for unauthenticated clients).

    Usage::

        limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)
        allowed, retry_after = limiter.check("some-key")
        if not allowed:
            raise HTTPException(429, headers={"Retry-After": str(retry_after)})
    """

    def __init__(self, *, max_requests: int, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, identifier: str) -> tuple[bool, float]:
        """Record a request for *identifier* and check whether it is allowed.

        Returns ``(allowed, retry_after_seconds)``.  When *allowed* is True
        the request was recorded and should proceed.  When False, *retry_after*
        is the number of seconds the caller must wait before the oldest request
        in the current window expires.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if identifier not in self._windows:
                self._windows[identifier] = deque()
            window = self._windows[identifier]
            # Evict timestamps outside the current window
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= self.max_requests:
                retry_after = self.window_seconds - (now - window[0])
                return False, max(0.0, retry_after)
            window.append(now)
            return True, 0.0
