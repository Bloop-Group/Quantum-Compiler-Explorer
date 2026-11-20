"""Lightweight Prometheus metrics collector and text exposition formatter."""

from __future__ import annotations

import threading
import time
from typing import Any


class MetricsCollector:
    """Thread-safe Prometheus metrics collector for Quantum Compiler Explorer."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests_total: dict[tuple[str, str, int], int] = {}
        self.transpile_requests: dict[tuple[str, str], int] = {}
        self.transpile_duration_sum: dict[tuple[str, str], float] = {}
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.rate_limited_total: int = 0
        self.active_workers: int = 0
        self.start_time: float = time.time()

    def record_request(self, method: str, endpoint: str, status_code: int) -> None:
        key = (method, endpoint, status_code)
        with self._lock:
            self.requests_total[key] = self.requests_total.get(key, 0) + 1

    def record_transpile(self, compiler: str, target_id: str, duration: float, cache_hit: bool) -> None:
        key = (compiler, target_id)
        with self._lock:
            self.transpile_requests[key] = self.transpile_requests.get(key, 0) + 1
            self.transpile_duration_sum[key] = self.transpile_duration_sum.get(key, 0.0) + duration
            if cache_hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

    def record_rate_limit(self) -> None:
        with self._lock:
            self.rate_limited_total += 1

    def render_prometheus(self) -> str:
        """Render metrics in Prometheus text exposition format (v0.0.4)."""
        lines = [
            "# HELP qce_uptime_seconds Total seconds since process startup",
            "# TYPE qce_uptime_seconds gauge",
            f"qce_uptime_seconds {time.time() - self.start_time:.1f}",
            "",
            "# HELP qce_http_requests_total Total HTTP requests handled",
            "# TYPE qce_http_requests_total counter",
        ]
        with self._lock:
            for (method, endpoint, status), count in sorted(self.requests_total.items()):
                lines.append(f'qce_http_requests_total{{method="{method}",endpoint="{endpoint}",status="{status}"}} {count}')

            lines.extend([
                "",
                "# HELP qce_transpilation_total Total transpilation operations executed",
                "# TYPE qce_transpilation_total counter",
            ])
            for (comp, tgt), count in sorted(self.transpile_requests.items()):
                lines.append(f'qce_transpilation_total{{compiler="{comp}",target="{tgt}"}} {count}')

            lines.extend([
                "",
                "# HELP qce_transpilation_duration_seconds_total Total duration spent transpiling",
                "# TYPE qce_transpilation_duration_seconds_total counter",
            ])
            for (comp, tgt), dur in sorted(self.transpile_duration_sum.items()):
                lines.append(f'qce_transpilation_duration_seconds_total{{compiler="{comp}",target="{tgt}"}} {dur:.4f}')

            lines.extend([
                "",
                "# HELP qce_cache_hits_total Total result cache hits",
                "# TYPE qce_cache_hits_total counter",
                f"qce_cache_hits_total {self.cache_hits}",
                "",
                "# HELP qce_cache_misses_total Total result cache misses",
                "# TYPE qce_cache_misses_total counter",
                f"qce_cache_misses_total {self.cache_misses}",
                "",
                "# HELP qce_rate_limited_total Total requests rejected by sliding-window rate limiter",
                "# TYPE qce_rate_limited_total counter",
                f"qce_rate_limited_total {self.rate_limited_total}",
            ])
        return "\n".join(lines) + "\n"


METRICS = MetricsCollector()
