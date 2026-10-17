"""Server-sent events encoding for the job event stream."""

from __future__ import annotations

import json
from collections.abc import Iterator

from gamelink.pipeline.events import Event

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def encode(event: Event) -> str:
    payload = json.dumps(event.to_dict(), ensure_ascii=False)
    return f"id: {event.seq}\nevent: {event.type}\ndata: {payload}\n\n"


def keep_alive() -> str:
    return ": keep-alive\n\n"


def frames(events: Iterator[Event | None]) -> Iterator[str]:
    """Turn a stream of events (with ``None`` as keep-alive) into SSE frames."""
    for event in events:
        yield keep_alive() if event is None else encode(event)
