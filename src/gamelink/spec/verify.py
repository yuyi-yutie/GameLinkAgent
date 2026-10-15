"""Consistency verification (dev_plan_1.md §4.5).

Because analysis is LLM-driven, we add a cheap "ground truth" check: run headless
Godot to introspect what RPCs / synchronizers / spawners actually exist in a
project, then compare against the spec to catch hallucinations and omissions.

If Godot is unavailable the check degrades to a single warning instead of failing.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gamelink.resources import template_path

_OUTPUT_MARKER = "GAMELINK_FACTS_JSON"
_STAGED_SCRIPT = "_gamelink_introspect.gd"


@dataclass
class Issue:
    severity: str  # "error" | "warning" | "info"
    message: str


def collect_engine_facts(
    project_dir: str | Path,
    godot_bin: str | None,
    timeout: int = 120,
) -> dict[str, Any] | None:
    """Introspect a Godot project via the engine. Returns ``None`` if unavailable."""
    if not godot_bin or not Path(godot_bin).exists():
        return None
    script = template_path("godot", "introspect.gd")
    if not script.exists():
        return None
    root = Path(project_dir)
    staged = root / _STAGED_SCRIPT
    try:
        shutil.copyfile(script, staged)
        proc = subprocess.run(
            [godot_bin, "--headless", "--path", str(root), "--script", f"res://{_STAGED_SCRIPT}"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        staged.unlink(missing_ok=True)
    match = re.search(rf"{_OUTPUT_MARKER}\s*:\s*(\{{.*\}})", proc.stdout, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def verify_consistency(
    project_dir: str | Path,
    protocol: dict[str, Any],
    architecture: dict[str, Any],
    godot_bin: str | None = None,
) -> list[Issue]:
    """Compare a spec against engine facts and report mismatches."""
    facts = collect_engine_facts(project_dir, godot_bin)
    if facts is None:
        return [
            Issue(
                "warning",
                "engine verification skipped (Godot not configured or introspection failed); "
                "set GAMELINK_GODOT_BIN to enable ground-truth checks",
            )
        ]

    issues: list[Issue] = []
    engine_rpcs = {m["name"] for m in facts.get("rpc_methods", []) if "name" in m}
    engine_autoloads = set(facts.get("autoloads", []))

    spec_rpc_ids = {m.get("id") for m in protocol.get("messages", []) if m.get("id")}
    for missing in sorted(spec_rpc_ids - engine_rpcs):
        issues.append(Issue("warning", f"spec message '{missing}' has no matching RPC in project"))
    for unused in sorted(engine_rpcs - spec_rpc_ids):
        issues.append(Issue("info", f"project RPC '{unused}' is absent from the spec (omission?)"))

    for name in architecture.get("scene", {}).get("autoloads", []):
        if name not in engine_autoloads:
            issues.append(Issue("warning", f"spec autoload '{name}' does not exist in the project"))

    return issues or [Issue("info", "spec is consistent with engine facts")]
