"""Analysis orchestration: project + options -> report + two validated specs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from gamelink.analyze.llm import CONTENT, LLMClient
from gamelink.analyze.prompts import build_analysis_prompt
from gamelink.config import Settings
from gamelink.errors import AnalysisError
from gamelink.ingest import GodotProject
from gamelink.options import DesignerOptions
from gamelink.spec.io import (
    ARCHITECTURE_SCHEMA,
    PROTOCOL_SCHEMA,
    load_schema,
    validate_architecture,
    validate_protocol,
)
from gamelink.util import extract_json


@dataclass
class AnalysisResult:
    report: str
    protocol_spec: dict[str, Any]
    architecture_spec: dict[str, Any]


class Analyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = LLMClient(settings.llm)

    def analyze(
        self,
        project: GodotProject,
        options: DesignerOptions,
        on_chunk: Callable[[str, str], None] | None = None,
    ) -> AnalysisResult:
        system, user = build_analysis_prompt(
            project_summary=project.summary(),
            options=options,
            protocol_schema=load_schema(PROTOCOL_SCHEMA),
            architecture_schema=load_schema(ARCHITECTURE_SCHEMA),
        )
        parts: list[str] = []
        for kind, text in self.llm.stream(system, user):
            if kind == CONTENT:
                parts.append(text)
            if on_chunk is not None:
                on_chunk(kind, text)
        data = extract_json("".join(parts))

        protocol = data.get("protocol_spec")
        architecture = data.get("architecture_spec")
        if not isinstance(protocol, dict) or not isinstance(architecture, dict):
            raise AnalysisError("LLM reply is missing 'protocol_spec' or 'architecture_spec'")

        validate_protocol(protocol)
        validate_architecture(architecture)
        return AnalysisResult(
            report=str(data.get("report", "")),
            protocol_spec=protocol,
            architecture_spec=architecture,
        )
