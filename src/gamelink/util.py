"""Small shared helpers."""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections.abc import Iterator
from typing import Any

from gamelink.errors import AnalysisError, JobCancelled

_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def slugify(text: str) -> str:
    """Turn an arbitrary string into a filesystem/identifier-friendly slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "project"


def _balanced_objects(text: str) -> Iterator[str]:
    """Yield every top-level ``{...}`` span, ignoring braces inside strings.

    Tracking string state (and escapes) matters because a report string often
    contains ``{`` / ``}`` characters, and naive slicing truncates the JSON.
    """
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0:
                yield text[start : index + 1]


def extract_json(text: str) -> dict[str, Any]:
    """Extract the JSON object from an LLM reply.

    Tolerates ```json fences, surrounding prose, and a few common malformations
    (stray trailing commas). Candidates are scanned with a string-aware brace
    matcher instead of naive ``first { .. last }`` slicing.
    """
    candidates = list(_balanced_objects(text))
    if not candidates:
        raise AnalysisError("LLM reply contained no JSON object")

    first_error: str | None = None
    parsed: list[dict[str, Any]] = []
    for candidate in candidates:
        for attempt in (candidate, _TRAILING_COMMA.sub(r"\1", candidate)):
            try:
                obj = json.loads(attempt)
            except json.JSONDecodeError as exc:
                if first_error is None:
                    first_error = str(exc)
                continue
            if isinstance(obj, dict):
                parsed.append(obj)
            break

    if not parsed:
        raise AnalysisError(f"LLM reply was not valid JSON: {first_error}")
    for obj in parsed:
        if "report" in obj or "protocol_spec" in obj:
            return obj
    return parsed[0]


def run_capture(
    cmd: list[str],
    timeout: float,
    cancel_event: threading.Event | None = None,
    poll: float = 0.5,
) -> subprocess.CompletedProcess:
    """Run ``cmd`` and capture its output, killing it early when cancelled.

    Same contract as ``subprocess.run(..., capture_output=True, text=True)`` plus
    an optional cancellation token — needed because a Godot export can take
    minutes, and a cancelled job must not leave the process running.
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=poll)
            except subprocess.TimeoutExpired:
                if cancel_event is not None and cancel_event.is_set():
                    raise JobCancelled("已取消") from None
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(cmd, timeout) from None
                continue
            return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
