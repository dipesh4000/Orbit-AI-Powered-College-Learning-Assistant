"""Bounded, process-local metrics and rotating metadata-only JSON logs."""

import json
import logging
import os
from collections import defaultdict
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from threading import Lock
from time import monotonic

from .config import ROOT

request_id = ContextVar("request_id", default=None)
_lock = Lock()
_started = monotonic()
_metrics = defaultdict(
    lambda: {
        "count": 0,
        "errors": 0,
        "total_ms": 0.0,
        "max_ms": 0.0,
        "cache_hits": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "buckets": [0] * 6,
    }
)
_bounds = [100, 500, 1000, 5000, 30000]
_logger = logging.getLogger("orbit.metrics")
_logger.setLevel(logging.INFO)
_logger.propagate = False


def record(event, name, duration_ms, *, error=False, **fields):
    # Callers supply fixed route templates/tool names, never request bodies or IDs.
    with _lock:
        row = _metrics[(event, name)]
        row["count"] += 1
        row["errors"] += int(error)
        row["total_ms"] += duration_ms
        row["max_ms"] = max(row["max_ms"], duration_ms)
        row["cache_hits"] += int(fields.get("cache_hit", False))
        row["input_tokens"] += fields.get("input_tokens", 0) or 0
        row["output_tokens"] += fields.get("output_tokens", 0) or 0
        bucket = next((i for i, bound in enumerate(_bounds) if duration_ms <= bound), 5)
        row["buckets"][bucket] += 1
        try:
            if not _logger.handlers:
                if os.environ.get("VERCEL") == "1":
                    handler = logging.StreamHandler()
                else:
                    folder = ROOT / "logs"
                    folder.mkdir(exist_ok=True)
                    handler = RotatingFileHandler(
                        folder / "metrics.jsonl",
                        maxBytes=5_000_000,
                        backupCount=3,
                        encoding="utf-8",
                    )
                handler.setFormatter(logging.Formatter("%(message)s"))
                _logger.addHandler(handler)
            _logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "request_id": request_id.get(),
                        "event": event,
                        "name": name,
                        "duration_ms": round(duration_ms, 2),
                        "error": bool(error),
                        **fields,
                    }
                )
            )
        except OSError:
            # A log directory problem must not fail a student request.
            pass


def snapshot():
    with _lock:
        return {
            "scope": "current server process",
            "uptime_seconds": round(monotonic() - _started),
            "latency_bucket_upper_ms": [*_bounds, "+Inf"],
            "metrics": [
                {
                    "event": event,
                    "name": name,
                    **row,
                    "buckets": list(row["buckets"]),
                    "mean_ms": round(row["total_ms"] / row["count"], 2),
                }
                for (event, name), row in sorted(_metrics.items())
            ],
        }
