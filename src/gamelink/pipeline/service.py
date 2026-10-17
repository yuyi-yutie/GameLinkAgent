"""Shared pipeline orchestration used by both the CLI and the web API.

Every entry point reports progress through an :class:`Emitter` and returns plain
domain objects, so callers render results their own way. Nothing here prints, and
nothing resolves paths against the process working directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gamelink.analyze import Analyzer
from gamelink.analyze.llm import REASONING
from gamelink.config import Settings
from gamelink.deploy import DeployPlan, DeployResult, build_deploy_plan, package
from gamelink.generate import GenerateResult, generate_server
from gamelink.ingest import GodotProject
from gamelink.options import DesignerOptions
from gamelink.pipeline.events import Emitter
from gamelink.spec import Issue, load_yaml, read_specs, verify_consistency, write_specs
from gamelink.spec.io import dump_yaml
from gamelink.util import slugify

__all__ = [
    "OPTIONS_FILE",
    "AnalyzeOutcome",
    "DeployOutcome",
    "analyze_project",
    "deploy_server",
    "generate_from_specs",
    "inspect_project",
    "verify_project",
    "write_report",
]

OPTIONS_FILE = "gamelink.options.yaml"


@dataclass
class AnalyzeOutcome:
    """Everything one analysis run produced."""

    report: str
    report_path: Path
    protocol_spec: dict[str, Any]
    architecture_spec: dict[str, Any]
    spec_paths: list[Path] = field(default_factory=list)


@dataclass
class DeployOutcome:
    plan: DeployPlan
    result: DeployResult


def _rel(path: str | Path, root: str | Path) -> str:
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


def write_report(out_dir: str | Path, project_name: str, report: str) -> Path:
    """Write the analysis report as Markdown and return its path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{slugify(project_name)}-report.md"
    path.write_text((report or "(无报告)").rstrip() + "\n", encoding="utf-8")
    return path


def inspect_project(project: str | Path, emit: Emitter | None = None) -> GodotProject:
    """Discover a Godot project. No LLM involved."""
    emitter = emit or Emitter()
    emitter.stage_started("inspect", project=str(project))
    found = GodotProject.discover(project)
    emitter.stage_finished(
        "inspect",
        name=found.name,
        root=str(found.root),
        scripts=len(found.scripts),
        scenes=len(found.scenes),
        resources=len(found.resources),
        autoloads=sorted(found.autoloads),
    )
    return found


def analyze_project(
    project: GodotProject,
    options: DesignerOptions,
    settings: Settings,
    emit: Emitter | None = None,
    *,
    out_dir: str | Path = "specs",
    emit_specs: bool = False,
) -> AnalyzeOutcome:
    """Run the LLM analysis and write the report (and optionally the two specs)."""
    emitter = emit or Emitter()
    emitter.stage_started("analyze", project=project.name, options=options.to_dict())
    emitter.progress("analyze", "正在调用 LLM 分析工程…")

    def on_chunk(kind: str, text: str) -> None:
        emitter.chunk("analyze", kind, text)
        emitter.check_cancelled()

    result = Analyzer(settings).analyze(project, options, on_chunk=on_chunk)

    out = Path(out_dir)
    report_path = write_report(out, project.name, result.report)
    emitter.artifact("analyze", report_path, "report", "分析报告")

    spec_paths: list[Path] = []
    if emit_specs:
        protocol_path, architecture_path = write_specs(
            result.protocol_spec, result.architecture_spec, out
        )
        options_path = dump_yaml(options.to_dict(), out / OPTIONS_FILE)
        spec_paths = [protocol_path, architecture_path]
        emitter.artifact("analyze", protocol_path, "protocol-spec", "协议规格")
        emitter.artifact("analyze", architecture_path, "architecture-spec", "服务端架构规格")
        emitter.artifact("analyze", options_path, "options", "生成选项")

    emitter.stage_finished(
        "analyze",
        report=str(report_path),
        specs=[str(path) for path in spec_paths],
        out=str(out),
        reasoning_kind=REASONING,
    )
    return AnalyzeOutcome(
        report=result.report,
        report_path=report_path,
        protocol_spec=result.protocol_spec,
        architecture_spec=result.architecture_spec,
        spec_paths=spec_paths,
    )


def generate_from_specs(
    project: GodotProject,
    specs_dir: str | Path,
    out_dir: str | Path,
    emit: Emitter | None = None,
) -> GenerateResult:
    """Generate a runnable Godot server project from reviewed specs."""
    emitter = emit or Emitter()
    emitter.stage_started("generate", project=project.name, specs=str(specs_dir), out=str(out_dir))

    protocol, architecture = read_specs(specs_dir)
    options_path = Path(specs_dir) / OPTIONS_FILE
    options = (
        DesignerOptions.from_dict(load_yaml(options_path))
        if options_path.exists()
        else DesignerOptions()
    )

    result = generate_server(project, options, protocol, architecture, out_dir)
    for path in result.files:
        emitter.artifact("generate", path, "file", _rel(path, result.out_dir))
    for todo in result.todos:
        emitter.todo(todo, stage="generate")
    emitter.stage_finished(
        "generate",
        files=len(result.files),
        todos=len(result.todos),
        out=str(result.out_dir),
    )
    return result


def verify_project(
    project: str | Path,
    specs_dir: str | Path,
    settings: Settings,
    emit: Emitter | None = None,
) -> list[Issue]:
    """Check the specs against ground truth introspected from the engine."""
    emitter = emit or Emitter()
    emitter.stage_started("verify", project=str(project), specs=str(specs_dir))
    emitter.progress("verify", "正在用 Godot 内省校验规格与实现…")

    protocol, architecture = read_specs(specs_dir)
    emitter.check_cancelled()
    issues = verify_consistency(
        project,
        protocol,
        architecture,
        settings.godot_bin,
        cancel_event=emitter.cancel_event,
    )
    for issue in issues:
        emitter.issue(issue.severity, issue.message, stage="verify")
    emitter.stage_finished(
        "verify",
        issues=len(issues),
        problems=sum(1 for issue in issues if issue.severity != "info"),
        checked=bool(settings.godot_bin),
    )
    return issues


def deploy_server(
    server_dir: str | Path,
    settings: Settings,
    emit: Emitter | None = None,
    *,
    out_dir: str | Path | None = None,
) -> DeployOutcome:
    """Export the headless server and package it with the deployment guide."""
    emitter = emit or Emitter()
    emitter.stage_started("deploy", server=str(server_dir))

    plan = build_deploy_plan(server_dir, settings, DesignerOptions(), out_dir=out_dir)
    emitter.log("一键部署：导出 headless 服务端", "title", stage="deploy")
    for line in plan.describe().splitlines():
        emitter.log(line.strip().removeprefix("- "), "info", stage="deploy")

    emitter.progress("deploy", "正在导出 Godot 服务端（首次导出较慢）…")
    result = package(plan, settings.godot_bin, cancel_event=emitter.cancel_event)
    for path in result.files:
        emitter.artifact("deploy", path, "file", _rel(path, result.dist_dir))
    emitter.stage_finished("deploy", files=len(result.files), dist=str(result.dist_dir))
    return DeployOutcome(plan=plan, result=result)
