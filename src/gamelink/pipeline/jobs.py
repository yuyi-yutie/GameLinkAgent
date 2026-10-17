"""Background jobs.

Run one pipeline stage on a worker thread and publish its events. Events are
appended to ``<job_dir>/events.jsonl`` as they happen, so a browser can reload or
reconnect and replay from any sequence number instead of losing a run that takes
minutes.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gamelink.config import Settings
from gamelink.errors import GameLinkError, JobCancelled
from gamelink.ingest import GodotProject
from gamelink.options import DesignerOptions
from gamelink.pipeline.events import ARTIFACT, PROGRESS, TODO, Emitter, Event
from gamelink.pipeline.service import (
    analyze_project,
    deploy_server,
    generate_from_specs,
    inspect_project,
    verify_project,
)

__all__ = ["JOB_KINDS", "Job", "JobManager"]

JOB_KINDS = ("inspect", "analyze", "generate", "verify", "deploy")

REQUIRED_PARAMS = {
    "inspect": ("project",),
    "analyze": ("project",),
    "generate": ("project",),
    "verify": ("project",),
    "deploy": ("server",),
}

QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELLED = "cancelled"
INTERRUPTED = "interrupted"

ACTIVE_STATUSES = (QUEUED, RUNNING)

_EVENTS = "events.jsonl"
_META = "job.json"


@dataclass
class Job:
    id: str
    kind: str
    params: dict[str, Any]
    status: str = QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    error_kind: str | None = None
    artifacts: list[dict[str, str]] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    progress: str = ""
    seq: int = 0
    dir: Path | None = None
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    subscribers: set[queue.Queue] = field(default_factory=set, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "params": self.params,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "error_kind": self.error_kind,
            "artifacts": self.artifacts,
            "todos": self.todos,
            "progress": self.progress,
            "seq": self.seq,
        }


class JobManager:
    """Owns the job registry, the worker threads and the event log."""

    def __init__(self, workspace: str | Path, settings: Settings | None = None) -> None:
        self.workspace = Path(workspace)
        self.jobs_dir = self.workspace / ".gamelink" / "jobs"
        self._settings = settings
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._load_existing()

    def settings(self) -> Settings:
        return self._settings if self._settings is not None else Settings.load(self.workspace / ".env")

    # -- registry ----------------------------------------------------------
    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 50) -> list[Job]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
        return jobs[:limit]

    def submit(self, kind: str, params: dict[str, Any]) -> Job:
        if kind not in JOB_KINDS:
            raise ValueError(f"unknown job kind: {kind}")
        missing = [name for name in REQUIRED_PARAMS.get(kind, ()) if not params.get(name)]
        if missing:
            raise ValueError(f"{kind} 缺少参数：{', '.join(missing)}")
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, params=params)
        job.dir = self.jobs_dir / job.id
        with self._lock:
            self._jobs[job.id] = job
        job.dir.mkdir(parents=True, exist_ok=True)
        self._write_meta(job)
        thread = threading.Thread(
            target=self._run,
            args=(job,),
            name=f"gamelink-{job.id}",
            daemon=True,
        )
        thread.start()
        return job

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or not job.active:
            return False
        job.cancel.set()
        return True

    # -- events ------------------------------------------------------------
    def replay(self, job: Job, from_seq: int = 0) -> list[Event]:
        """Read the persisted event log, skipping anything at or before ``from_seq``."""
        path = job.dir / _EVENTS if job.dir is not None else None
        if path is None or not path.is_file():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        events: list[Event] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                event = Event.from_dict(json.loads(line))
            except json.JSONDecodeError:
                continue
            if event.seq > from_seq:
                events.append(event)
        return events

    def attach(self, job: Job) -> queue.Queue:
        subscriber: queue.Queue = queue.Queue()
        with job.lock:
            job.subscribers.add(subscriber)
        return subscriber

    def detach(self, job: Job, subscriber: queue.Queue) -> None:
        with job.lock:
            job.subscribers.discard(subscriber)

    def stream(self, job: Job, from_seq: int = 0, idle: float = 15.0) -> Iterator[Event | None]:
        """Replay stored events past ``from_seq``, then follow live ones.

        Yields ``None`` as a keep-alive whenever nothing happens for ``idle`` seconds.
        """
        subscriber = self.attach(job)
        last = from_seq
        try:
            for event in self.replay(job, from_seq):
                last = max(last, event.seq)
                yield event
            if not job.active:
                return
            while True:
                try:
                    item = subscriber.get(timeout=idle)
                except queue.Empty:
                    if not job.active:
                        return
                    yield None
                    continue
                if item is None:
                    return
                if item.seq <= last:
                    continue
                last = item.seq
                yield item
                if item.terminal:
                    return
        finally:
            self.detach(job, subscriber)

    # -- worker ------------------------------------------------------------
    def _run(self, job: Job) -> None:
        job.status = RUNNING
        job.started_at = time.time()
        self._write_meta(job)

        def sink(event: Event) -> None:
            with job.lock:
                job.seq = event.seq
                self._record(job, event)
            for subscriber in list(job.subscribers):
                subscriber.put(event)

        emit = Emitter(sink, job.cancel)
        try:
            self._dispatch(job, emit)
            emit.finished(status=SUCCEEDED, artifacts=len(job.artifacts), todos=len(job.todos))
            job.status = SUCCEEDED
        except JobCancelled:
            emit.cancelled_event()
            job.status = CANCELLED
        except GameLinkError as exc:
            job.error = str(exc)
            job.error_kind = type(exc).__name__
            emit.failed(str(exc), type(exc).__name__)
            job.status = FAILED
        except Exception as exc:  # a crashed worker must still terminate the stream
            job.error = str(exc)
            job.error_kind = type(exc).__name__
            emit.failed(str(exc), type(exc).__name__)
            job.status = FAILED
        finally:
            job.finished_at = time.time()
            self._write_meta(job)
            for subscriber in list(job.subscribers):
                subscriber.put(None)

    def _dispatch(self, job: Job, emit: Emitter) -> None:
        params = job.params
        settings = self.settings()
        if job.kind == "inspect":
            inspect_project(params["project"], emit)
        elif job.kind == "analyze":
            analyze_project(
                GodotProject.discover(params["project"]),
                DesignerOptions.from_dict(params.get("options") or {}),
                settings,
                emit,
                out_dir=params.get("out") or self.workspace / "specs",
                emit_specs=bool(params.get("emit_specs", True)),
            )
        elif job.kind == "generate":
            generate_from_specs(
                GodotProject.discover(params["project"]),
                params.get("specs") or self.workspace / "specs",
                params.get("out") or self.workspace / "out" / "server",
                emit,
            )
        elif job.kind == "verify":
            verify_project(
                params["project"],
                params.get("specs") or self.workspace / "specs",
                settings,
                emit,
            )
        elif job.kind == "deploy":
            deploy_server(params["server"], settings, emit, out_dir=params.get("out"))
        else:
            raise ValueError(f"unknown job kind: {job.kind}")

    # -- persistence -------------------------------------------------------
    def _record(self, job: Job, event: Event) -> None:
        if event.type == PROGRESS and event.data.get("message"):
            job.progress = str(event.data["message"])
        elif event.type == ARTIFACT:
            job.artifacts.append(
                {
                    "path": str(event.data.get("path", "")),
                    "kind": str(event.data.get("kind", "")),
                    "label": str(event.data.get("label", "")),
                    "stage": str(event.stage or ""),
                }
            )
        elif event.type == TODO:
            job.todos.append(str(event.data.get("message", "")))
        self._append(job, event)

    def _append(self, job: Job, event: Event) -> None:
        if job.dir is None:
            return
        try:
            with (job.dir / _EVENTS).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _write_meta(self, job: Job) -> None:
        if job.dir is None:
            return
        try:
            job.dir.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(job.to_dict(), indent=2, ensure_ascii=False) + "\n"
            (job.dir / _META).write_text(payload, encoding="utf-8")
        except OSError:
            pass

    def _load_existing(self) -> None:
        if not self.jobs_dir.is_dir():
            return
        for path in sorted(self.jobs_dir.iterdir()):
            meta = path / _META
            if not path.is_dir() or not meta.is_file():
                continue
            try:
                payload = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            job = Job(
                id=str(payload.get("id") or path.name),
                kind=str(payload.get("kind") or ""),
                params=payload.get("params") or {},
                status=str(payload.get("status") or SUCCEEDED),
                created_at=float(payload.get("created_at") or 0.0),
                started_at=payload.get("started_at"),
                finished_at=payload.get("finished_at"),
                error=payload.get("error"),
                error_kind=payload.get("error_kind"),
                artifacts=payload.get("artifacts") or [],
                todos=payload.get("todos") or [],
                progress=str(payload.get("progress") or ""),
                seq=int(payload.get("seq") or 0),
                dir=path,
            )
            if job.status in ACTIVE_STATUSES:
                job.status = INTERRUPTED
                job.error = "服务重启，任务已中断"
            self._jobs[job.id] = job
