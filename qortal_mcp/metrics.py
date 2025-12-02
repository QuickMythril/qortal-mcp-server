"""Minimal in-process metrics recorder (not suitable for multi-process aggregation)."""

from __future__ import annotations

from collections import Counter
from threading import Lock
from typing import Dict


class MetricsRecorder:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests = 0
        self._request_durations_ms: Dict[str, float] = {}
        self._rate_limited = 0
        self._tool_success: Counter[str] = Counter()
        self._tool_error: Counter[str] = Counter()

    def incr_request(self) -> None:
        with self._lock:
            self._requests += 1

    def record_duration(self, request_id: str, duration_ms: float) -> None:
        with self._lock:
            self._request_durations_ms[request_id] = duration_ms

    def incr_rate_limited(self) -> None:
        with self._lock:
            self._rate_limited += 1

    def record_tool(self, tool: str, *, success: bool) -> None:
        with self._lock:
            if success:
                self._tool_success[tool] += 1
            else:
                self._tool_error[tool] += 1

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return {
                "requests": self._requests,
                "rate_limited": self._rate_limited,
                "tool_success": dict(self._tool_success),
                "tool_error": dict(self._tool_error),
                "recent_request_durations_ms": dict(self._request_durations_ms),
            }

    def reset(self) -> None:
        with self._lock:
            self._requests = 0
            self._request_durations_ms.clear()
            self._rate_limited = 0
            self._tool_success.clear()
            self._tool_error.clear()


default_metrics = MetricsRecorder()
