"""Structured JSON logging configuration for production observability."""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt) if self.datefmt else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_fields"):
            log_obj.update(getattr(record, "extra_fields"))
        return json.dumps(log_obj)


def setup_logging(json_logs: bool = False, level: int = logging.INFO) -> None:
    """Configure root logger with either standard or JSON structured formatting."""
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
