"""Lightweight sliding-window per-client rate limiter."""

from __future__ import annotations

from collections import deque
import threading
import time


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        self.max_requests = max(1, max_requests)
        self.window_seconds = max(0.1, window_seconds)
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def allow(self, client_key: str, now: float | None = None) -> bool:
        ts = time.monotonic() if now is None else now
        cutoff = ts - self.window_seconds
        with self._lock:
            bucket = self._hits.setdefault(client_key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(ts)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
