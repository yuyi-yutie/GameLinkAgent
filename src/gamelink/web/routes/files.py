"""Filesystem browsing, project inspection and artifact read/write."""

from __future__ import annotations

import string
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gamelink.errors import GameLinkError, SpecValidationError
from gamelink.ingest import GodotProject
from gamelink.spec.io import (
    ARCHITECTURE_FILENAME,
    PROTOCOL_FILENAME,
    validate_architecture,
    validate_protocol,
)
from gamelink.web.security import check_readable, resolve_in_workspace

router = APIRouter(prefix="/api")


def _drives() -> list[str]:
    return [f"{letter}:/" for letter in string.ascii_uppercase if Path(f"{letter}:/").exists()]


def _workspace_file(request: Request, raw: str) -> Path:
    try:
        target = resolve_in_workspace(request.app.state.workspace, raw)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return target


def _current_dir(request: Request, path: str | None) -> Path:
    workspace = request.app.state.workspace
    current = Path(path).expanduser() if path else workspace
    if not current.is_absolute():
        current = workspace / current
    return current.resolve()


def _browse(current: Path, *, include_files: bool) -> dict[str, Any]:
    if not current.is_dir():
        raise HTTPException(status_code=404, detail=f"不是目录：{current}")
    try:
        items = list(current.iterdir())
    except OSError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    children = sorted(
        (item for item in items if item.is_dir() and not item.name.startswith(".")),
        key=lambda item: item.name.lower(),
    )
    payload: dict[str, Any] = {
        "path": str(current),
        "name": current.name or str(current),
        "parent": str(current.parent) if current.parent != current else None,
        "is_project": (current / "project.godot").is_file(),
        "dirs": [{"name": item.name, "path": str(item)} for item in children],
        "roots": _drives(),
    }
    if include_files:
        executables = sorted(
            (item for item in items if item.is_file() and item.suffix.lower() == ".exe"),
            key=lambda item: item.name.lower(),
        )
        payload["files"] = [{"name": item.name, "path": str(item)} for item in executables]
    return payload


@router.get("/fs/dirs")
def list_dirs(request: Request, path: str | None = None) -> dict[str, Any]:
    """Browse directories so the user can point at a Godot project anywhere on disk."""
    return _browse(_current_dir(request, path), include_files=False)


@router.get("/fs/entries")
def list_entries(request: Request, path: str | None = None) -> dict[str, Any]:
    """Directory entries plus ``.exe`` files, for picking a Godot executable."""
    return _browse(_current_dir(request, path), include_files=True)


@router.get("/projects")
def inspect(request: Request, path: str) -> dict[str, Any]:
    try:
        found = GodotProject.discover(path)
    except GameLinkError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        **found.to_dict(),
        "file_tree": found.file_tree(),
        "counts": {
            "scripts": len(found.scripts),
            "scenes": len(found.scenes),
            "resources": len(found.resources),
        },
    }


def _validate_text(target: Path, text: str) -> None:
    if target.name not in (PROTOCOL_FILENAME, ARCHITECTURE_FILENAME):
        return
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"YAML 解析失败：{exc}") from exc
    validator = validate_protocol if target.name == PROTOCOL_FILENAME else validate_architecture
    try:
        validator(data)
    except SpecValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/artifacts")
def read_artifact(request: Request, path: str) -> dict[str, Any]:
    target = _workspace_file(request, path)
    try:
        check_readable(target)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在：{target}")
    return {
        "path": str(target),
        "name": target.name,
        "text": target.read_text(encoding="utf-8", errors="replace"),
    }


class ArtifactPayload(BaseModel):
    path: str
    text: str = Field(default="")


@router.put("/artifacts")
def write_artifact(request: Request, payload: ArtifactPayload) -> dict[str, Any]:
    target = _workspace_file(request, payload.path)
    try:
        check_readable(target)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    _validate_text(target, payload.text)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload.text, encoding="utf-8")
    return {"path": str(target), "bytes": len(payload.text.encode("utf-8"))}
