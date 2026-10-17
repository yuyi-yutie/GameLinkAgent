"""Event plumbing shared by the CLI and the web UI."""

import threading

import pytest

from gamelink.errors import JobCancelled
from gamelink.pipeline import (
    CHUNK,
    PROGRESS,
    STAGE_STARTED,
    Emitter,
    Event,
)


def collect() -> tuple[list[Event], Emitter]:
    events: list[Event] = []
    return events, Emitter(events.append)


def test_sequence_numbers_are_monotonic():
    events, emit = collect()
    emit.stage_started("analyze", project="snake")
    emit.progress("analyze", "working")
    emit.chunk("analyze", "content", "hi")
    emit.stage_finished("analyze")

    assert [event.type for event in events] == [
        STAGE_STARTED,
        PROGRESS,
        CHUNK,
        "stage_finished",
    ]
    assert [event.seq for event in events] == [1, 2, 3, 4]


def test_default_emitter_discards_events():
    emit = Emitter()
    emit.progress("verify", "no sink attached")
    assert emit.seq == 1


def test_event_round_trips_through_json():
    _, emit = collect()
    original = emit.artifact("generate", "out/scripts/main.gd", "file", "main.gd")
    restored = Event.from_dict(original.to_dict())

    assert restored == original
    assert restored.data["path"] == "out/scripts/main.gd"
    assert restored.data["label"] == "main.gd"


def test_check_cancelled_raises_only_after_cancel():
    emit = Emitter()
    emit.check_cancelled()

    emit.cancel()
    assert emit.cancelled() is True
    with pytest.raises(JobCancelled):
        emit.check_cancelled()


def test_emitter_shares_an_external_cancel_event():
    flag = threading.Event()
    emit = Emitter(None, flag)
    flag.set()
    with pytest.raises(JobCancelled):
        emit.check_cancelled()
