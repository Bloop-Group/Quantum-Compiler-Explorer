"""Content-addressed cache with Redis primary and thread-safe LRU fallback."""

from __future__ import annotations

from collections import OrderedDict
import json
import os
import threading
from typing import Any


class ResultCache:
    """Stores transpilation payloads keyed by SHA-256 content hashes."""

    def __init__(self, max_entries: int = 512, ttl_seconds: int = 3600, redis_url: str | None = None) -> None:
        self.max_entries = max(1, max_entries)
        self.ttl_seconds = max(1, ttl_seconds)
        self._lock = threading.Lock()
        self._lru: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._redis = None
        url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        if url:
            try:
                import redis  # type: ignore
                client = redis.from_url(url, decode_responses=True, socket_connect_timeout=1.0)
                client.ping()
                self._redis = client
            except Exception:
                self._redis = None

    @property
    def backend_name(self) -> str:
        return "redis" if self._redis is not None else "memory_lru"

    def get(self, key: str) -> dict[str, Any] | None:
        if self._redis is not None:
            try:
                raw = self._redis.get(f"qce:{key}")
                if raw is not None:
                    return json.loads(raw)
            except Exception:
                pass
        with self._lock:
            val = self._lru.get(key)
            if val is not None:
                self._lru.move_to_end(key)
                return dict(val)
        return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        if self._redis is not None:
            try:
                self._redis.setex(f"qce:{key}", self.ttl_seconds, json.dumps(value))
            except Exception:
                pass
        with self._lock:
            self._lru[key] = dict(value)
            self._lru.move_to_end(key)
            while len(self._lru) > self.max_entries:
                self._lru.popitem(last=False)
