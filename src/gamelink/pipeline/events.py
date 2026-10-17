"""Structured pipeline events.

The pipeline reports everything it does through an :class:`Emitter`, so one code
path can drive Rich output in the terminal *and* a streamed event feed in the web
UI. Neither side needs to know about the other.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from gamelink.errors import JobCancelled

__all__ = [
    "ARTIFACT",
    "CHUNK",
    "ISSUE",
    "JOB_CANCELLED",
    "JOB_FAILED",
    "JOB_FINISHED",
    "LOG",
    "PROGRESS",
    "STAGE_FINISHED",
    "STAGE_STARTED",
    "TERMINAL_TYPES",
    "TODO",
    "Emitter",
    "Event",
    "JobCancelled",
    "Sink",
    "Stage",
]

Stage = Literal["inspect", "analyze", "generate", "verify", "deploy"]

STAGE_STARTED = "stage_started"
PROGRESS = "progress"
CHUNK = "chunk"
ARTIFACT = "artifact"
LOG = "log"
ISSUE = "issue"
TODO = "todo"
STAGE_FINISHED = "stage_finished"
JOB_FAILED = "job_failed"
JOB_FINISHED = "job_finished"
JOB_CANCELLED = "job_cancelled"

TERMINAL_TYPES = frozenset({JOB_FAILED, JOB_FINISHED, JOB_CANCELLED})

LOG_LEVELS = ("info", "title", "warn", "error")
ISSUE_SEVERITIES = ("error", "warning", "info")

Sink = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    """One thing that happened, with a monotonic sequence number."""

    type: str
    seq: int
    ts: float
    stage: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def terminal(self) -> bool:
        return self.type in TERMINAL_TYPES

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "seq": self.seq,
            "ts": self.ts,
            "stage": self.stage,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Event:
        return cls(
            type=str(payload.get("type", "")),
            seq=int(payload.get("seq", 0)),
            ts=float(payload.get("ts", 0.0)),
            stage=payload.get("stage"),
            data=payload.get("data") or {},
        )


class Emitter:
    """Emits sequenced events to a sink and doubles as the cancellation token."""

    def __init__(
        self,
        sink: Sink | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self._sink = sink
        self._cancel = cancel_event if cancel_event is not None else threading.Event()
        self._seq = 0
        self._lock = threading.Lock()

    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel

    @property
    def seq(self) -> int:
        return self._seq

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()

    def check_cancelled(self) -> None:
        """Raise :class:`JobCancelled` if the caller asked to stop."""
        if self._cancel.is_set():
            raise JobCancelled("已取消")

    def emit(
        self,
        type_: str,
        stage: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> Event:
        with self._lock:
            self._seq += 1
            event = Event(type=type_, seq=self._seq, ts=time.time(), stage=stage, data=data or {})
        if self._sink is not None:
            self._sink(event)
        return event

    def stage_started(self, stage: Stage, **data: Any) -> Event:
        return self.emit(STAGE_STARTED, stage, data)

    def progress(self, stage: Stage, message: str, **data: Any) -> Event:
        return self.emit(PROGRESS, stage, {"message": message, **data})

    def chunk(self, stage: Stage, kind: str, text: str) -> Event:
        return self.emit(CHUNK, stage, {"kind": kind, "text": text})

    def artifact(self, stage: Stage, path: str | Path, kind: str, label: str = "") -> Event:
        target = str(path)
        return self.emit(
            ARTIFACT,
            stage,
            {"path": target, "kind": kind, "label": label or Path(target).name},
        )

    def log(self, message: str, level: str = "info", stage: str | None = None) -> Event:
        return self.emit(LOG, stage, {"level": level, "message": message})

    def issue(self, severity: str, message: str, stage: str | None = None) -> Event:
        return self.emit(ISSUE, stage, {"severity": severity, "message": message})

    def todo(self, message: str, stage: str | None = None) -> Event:
        return self.emit(TODO, stage, {"message": message})

    def stage_finished(self, stage: Stage, **data: Any) -> Event:
        return self.emit(STAGE_FINISHED, stage, data)

    def failed(self, error: str, kind: str = "GameLinkError") -> Event:
        return self.emit(JOB_FAILED, None, {"kind": kind, "error": error})

    def finished(self, **data: Any) -> Event:
        return self.emit(JOB_FINISHED, None, data)

    def cancelled_event(self) -> Event:
        return self.emit(JOB_CANCELLED, None, {"message": "已取消"})
