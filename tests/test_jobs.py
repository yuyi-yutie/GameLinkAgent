"""Background job execution, event persistence and cancellation."""

import json
import threading
import time
from pathlib import Path

import pytest

from gamelink.pipeline import jobs as jobs_module
from gamelink.pipeline.events import JOB_CANCELLED, JOB_FINISHED
from gamelink.pipeline.jobs import CANCELLED, FAILED, SUCCEEDED, JobManager

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "examples" / "snake-single"
SPECS = REPO / "examples" / "snake-specs"


def wait(job, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    while job.active and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not job.active, f"job {job.id} did not finish in time"
    return job


def test_inspect_job_succeeds_and_persists_events(tmp_path):
    manager = JobManager(tmp_path)
    job = wait(manager.submit("inspect", {"project": str(FIXTURE)}))

    assert job.status == SUCCEEDED
    assert job.error is None

    events = manager.replay(job)
    assert events[0].type == "stage_started"
    assert events[-1].type == JOB_FINISHED
    assert events[-1].terminal

    meta = json.loads((job.dir / "job.json").read_text(encoding="utf-8"))
    assert meta["status"] == SUCCEEDED
    assert meta["kind"] == "inspect"
    assert (job.dir / "events.jsonl").is_file()


def test_generate_job_records_artifacts(tmp_path):
    manager = JobManager(tmp_path)
    job = wait(
        manager.submit(
            "generate",
            {
                "project": str(FIXTURE),
                "specs": str(SPECS),
                "out": str(tmp_path / "out"),
            },
        )
    )

    assert job.status == SUCCEEDED, job.error
    paths = {artifact["path"] for artifact in job.artifacts}
    assert any(path.endswith("main.gd") for path in paths)


def test_replay_honours_from_seq(tmp_path):
    manager = JobManager(tmp_path)
    job = wait(manager.submit("inspect", {"project": str(FIXTURE)}))

    everything = manager.replay(job)
    tail = manager.replay(job, from_seq=1)
    assert len(tail) == len(everything) - 1
    assert all(event.seq > 1 for event in tail)


def test_stream_replays_then_ends_for_a_finished_job(tmp_path):
    manager = JobManager(tmp_path)
    job = wait(manager.submit("inspect", {"project": str(FIXTURE)}))

    seen = [event for event in manager.stream(job) if event is not None]
    assert seen[-1].terminal


def test_unknown_kind_and_missing_params_are_rejected(tmp_path):
    manager = JobManager(tmp_path)
    with pytest.raises(ValueError, match="unknown job kind"):
        manager.submit("teleport", {})
    with pytest.raises(ValueError, match="缺少参数"):
        manager.submit("analyze", {})


def test_failure_is_recorded(tmp_path):
    manager = JobManager(tmp_path)
    job = wait(manager.submit("inspect", {"project": str(tmp_path / "not-a-project")}))

    assert job.status == FAILED
    assert job.error and "project.godot" in job.error
    assert manager.replay(job)[-1].terminal


def test_cancel_stops_a_running_job(tmp_path, monkeypatch):
    entered = threading.Event()
    finished = threading.Event()

    def slow(project, emit=None):
        entered.set()
        for _ in range(600):
            time.sleep(0.01)
            emit.check_cancelled()
        finished.set()

    monkeypatch.setattr(jobs_module, "inspect_project", slow)
    manager = JobManager(tmp_path)
    job = manager.submit("inspect", {"project": "."})

    assert entered.wait(5), "worker never started"
    assert manager.cancel(job.id) is True
    wait(job)

    assert job.status == CANCELLED
    assert not finished.is_set()
    assert manager.replay(job)[-1].type == JOB_CANCELLED


def test_cancel_is_a_no_op_for_a_finished_job(tmp_path):
    manager = JobManager(tmp_path)
    job = wait(manager.submit("inspect", {"project": str(FIXTURE)}))
    assert manager.cancel(job.id) is False


def test_history_survives_a_restart(tmp_path):
    first = JobManager(tmp_path)
    job = wait(first.submit("inspect", {"project": str(FIXTURE)}))

    second = JobManager(tmp_path)
    reloaded = second.get(job.id)
    assert reloaded is not None
    assert reloaded.status == SUCCEEDED
    assert [item.id for item in second.list()] == [job.id]


def test_interrupted_jobs_are_marked_on_reload(tmp_path):
    manager = JobManager(tmp_path)
    job_dir = manager.jobs_dir / "stale"
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(
        json.dumps({"id": "stale", "kind": "analyze", "params": {}, "status": "running"}),
        encoding="utf-8",
    )

    reloaded = JobManager(tmp_path).get("stale")
    assert reloaded is not None
    assert reloaded.status == "interrupted"
    assert reloaded.error
