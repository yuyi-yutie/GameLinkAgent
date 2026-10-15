"""Ingest a Godot 4 project directory.

Produces a :class:`GodotProject` summarizing the project settings, autoloads,
scripts, scenes and resources, plus a compact textual digest suitable for an
LLM prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from gamelink.errors import IngestError

IGNORED_DIRS = {".godot", ".import", ".git", ".vs", ".vscode", "out", "__pycache__"}

_EXT_CATEGORIES = {
    ".gd": "scripts",
    ".tscn": "scenes",
    ".tres": "resources",
    ".gdshader": "shaders",
    ".cs": "scripts",
}

_PACKED_STRING_RE = re.compile(r'"([^"]*)"')


def parse_godot_config(text: str) -> dict[str, str]:
    """Parse the INI-like ``project.godot`` into flat ``section/key`` -> value keys."""
    section = ""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            full = f"{section}/{key}" if section else key
            out[full] = value.strip()
    return out


def _strip_quotes(value: str) -> str:
    return value.strip().strip('"')


@dataclass
class GodotProject:
    """A discovered Godot project."""

    root: Path
    config_path: Path
    name: str
    features: list[str] = field(default_factory=list)
    main_scene: str | None = None
    autoloads: dict[str, str] = field(default_factory=dict)
    scripts: list[Path] = field(default_factory=list)
    scenes: list[Path] = field(default_factory=list)
    resources: list[Path] = field(default_factory=list)
    shaders: list[Path] = field(default_factory=list)
    other: list[Path] = field(default_factory=list)

    # -- discovery ---------------------------------------------------------
    @classmethod
    def discover(cls, path: str | Path) -> GodotProject:
        target = Path(path).resolve()
        root = target if target.is_dir() else target.parent
        config_path = root / "project.godot"
        if not config_path.is_file():
            raise IngestError(f"not a Godot project (missing project.godot): {root}")

        cfg = parse_godot_config(config_path.read_text(encoding="utf-8", errors="replace"))
        project = cls(
            root=root,
            config_path=config_path,
            name=_strip_quotes(cfg.get("application/config/name", root.name)) or root.name,
            features=_PACKED_STRING_RE.findall(cfg.get("application/config/features", "")),
            main_scene=_strip_quotes(cfg.get("application/run/main_scene", "")) or None,
            autoloads={
                key.split("/", 1)[1]: value
                for key, value in cfg.items()
                if key.startswith("autoload/")
            },
        )
        project._collect_files()
        return project

    def _collect_files(self) -> None:
        buckets: dict[str, list[Path]] = {name: [] for name in set(_EXT_CATEGORIES.values())}
        other: list[Path] = []
        for item in sorted(self.root.rglob("*")):
            if not item.is_file():
                continue
            if any(part in IGNORED_DIRS for part in item.relative_to(self.root).parts):
                continue
            category = _EXT_CATEGORIES.get(item.suffix)
            if category:
                buckets[category].append(item)
            elif item.name == "project.godot":
                continue
            else:
                other.append(item)
        self.scripts = buckets["scripts"]
        self.scenes = buckets["scenes"]
        self.resources = buckets["resources"]
        self.shaders = buckets["shaders"]
        self.other = other

    # -- presentation ------------------------------------------------------
    def file_tree(self) -> list[str]:
        rels = sorted(
            str(p.relative_to(self.root)).replace("\\", "/")
            for p in [self.config_path, *self.scripts, *self.scenes, *self.resources, *self.shaders]
        )
        return rels

    def read(self, path: Path, max_chars: int = 20000) -> str:
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n# ... truncated ({len(text)} chars total)"
        return text

    def summary(self, max_total_chars: int = 60000) -> str:
        """A textual digest of the project, suitable for an LLM prompt."""
        lines: list[str] = [
            f"# Godot project: {self.name}",
            f"engine_features: {', '.join(self.features) or 'unknown'}",
            f"main_scene: {self.main_scene or 'unspecified'}",
            f"autoloads: {self.autoloads or '{}'}",
            "",
            "## File tree",
            *self.file_tree(),
            "",
        ]
        for label, files in (
            ("GDScript files", self.scripts),
            ("Scenes (.tscn)", self.scenes),
            ("Resources (.tres)", self.resources),
        ):
            for path in files:
                rel = str(path.relative_to(self.root)).replace("\\", "/")
                lines.append(f"## {label} — {rel}")
                lines.append("```")
                lines.append(self.read(path))
                lines.append("```")
                lines.append("")
        digest = "\n".join(lines)
        if len(digest) > max_total_chars:
            digest = digest[:max_total_chars] + "\n\n# ... digest truncated"
        return digest

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "name": self.name,
            "features": self.features,
            "main_scene": self.main_scene,
            "autoloads": self.autoloads,
            "scripts": [str(p.relative_to(self.root)) for p in self.scripts],
            "scenes": [str(p.relative_to(self.root)) for p in self.scenes],
            "resources": [str(p.relative_to(self.root)) for p in self.resources],
        }
