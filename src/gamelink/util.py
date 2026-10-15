"""Small shared helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from gamelink.errors import AnalysisError


def slugify(text: str) -> str:
    """Turn an arbitrary string into a filesystem/identifier-friendly slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "project"


def extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM reply.

    Tolerates ```json fences and surrounding prose.
    """
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise AnalysisError("LLM reply contained no JSON object")
        candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise AnalysisError(f"LLM reply was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AnalysisError("LLM reply JSON was not an object")
    return parsed
