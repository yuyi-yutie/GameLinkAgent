"""Locate bundled resources (JSON Schemas and code templates).

Schemas live under ``gamelink/schemas`` and templates under
``gamelink/templates`` inside the installed package, so they resolve the same
way in a source checkout and in an installed wheel.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def package_root() -> Path:
    """Return the filesystem path of the installed ``gamelink`` package."""
    return Path(str(resources.files("gamelink")))


def schema_path(name: str) -> Path:
    """Path to a JSON Schema file, e.g. ``schema_path("protocol.spec.schema.json")``."""
    return package_root() / "schemas" / name


def templates_root() -> Path:
    """Directory containing engine template folders."""
    return package_root() / "templates"


def template_path(*parts: str) -> Path:
    """Path to a template file, e.g. ``template_path("godot", "NetworkManager.gd.tmpl")``."""
    return templates_root().joinpath(*parts)
