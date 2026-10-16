"""Structured task log: what happened, in order, for the log pane and exports."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

LEVEL_INFO = "info"
LEVEL_SUCCESS = "success"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"

_LEVEL_LABELS = {
    LEVEL_INFO: "信息",
    LEVEL_SUCCESS: "完成",
    LEVEL_WARNING: "注意",
    LEVEL_ERROR: "错误",
}


@dataclass(frozen=True)
class LogRecord:
    level: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""

    @property
    def level_label(self) -> str:
        return _LEVEL_LABELS.get(self.level, self.level)

    def line(self) -> str:
        stamp = self.timestamp.strftime("%H:%M:%S")
        prefix = f"[{self.level_label}]"
        body = f"{self.source} — {self.message}" if self.source else self.message
        return f"{stamp} {prefix} {body}"


class TaskLog:
    """In-memory, bounded log with change notification."""

    def __init__(self, limit: int = 800) -> None:
        self._records: list[LogRecord] = []
        self._limit = limit
        self._listeners: list = []

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def add(self, level: str, message: str, source: str = "") -> LogRecord:
        record = LogRecord(level=level, message=message, source=source)
        self._records.append(record)
        if len(self._records) > self._limit:
            del self._records[: len(self._records) - self._limit]
        for listener in self._listeners:
            listener(record)
        return record

    def info(self, message: str, source: str = "") -> LogRecord:
        return self.add(LEVEL_INFO, message, source)

    def success(self, message: str, source: str = "") -> LogRecord:
        return self.add(LEVEL_SUCCESS, message, source)

    def warning(self, message: str, source: str = "") -> LogRecord:
        return self.add(LEVEL_WARNING, message, source)

    def error(self, message: str, source: str = "") -> LogRecord:
        return self.add(LEVEL_ERROR, message, source)

    def records(self) -> tuple[LogRecord, ...]:
        return tuple(self._records)

    def text(self) -> str:
        return "\n".join(record.line() for record in self._records)

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)


def elapsed_label(started: float) -> str:
    return f"{time.perf_counter() - started:.2f}s"
