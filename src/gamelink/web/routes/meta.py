"""Environment status, designer options, JSON Schemas and configuration."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from gamelink import __version__
from gamelink.config import Settings, save_user_config, user_config_path
from gamelink.options import OPTION_CHOICES, DesignerOptions
from gamelink.resources import static_root
from gamelink.spec.io import ARCHITECTURE_SCHEMA, PROTOCOL_SCHEMA, load_schema

router = APIRouter(prefix="/api")

_SCHEMAS = {
    "protocol": PROTOCOL_SCHEMA,
    "architecture": ARCHITECTURE_SCHEMA,
}


def settings_for(request: Request) -> Settings:
    return request.app.state.jobs.settings()


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    settings = settings_for(request)
    godot = settings.godot_bin
    return {
        "version": __version__,
        "workspace": str(request.app.state.workspace),
        "python": platform.python_version(),
        "llm": {
            "model": settings.llm.model,
            "base_url": settings.llm.base_url,
            "configured": settings.llm_configured,
        },
        "godot": {
            "bin": godot,
            "configured": bool(godot),
            "exists": bool(godot) and Path(godot).exists(),
        },
        "deploy": {"host": settings.deploy.host, "game_port": settings.deploy.game_port},
        "user_config": str(user_config_path()),
        "ui_built": (static_root() / "index.html").is_file(),
    }


@router.get("/options")
def options() -> dict[str, Any]:
    return {"choices": OPTION_CHOICES, "defaults": DesignerOptions().to_dict()}


@router.get("/schemas/{name}")
def schema(name: str) -> dict[str, Any]:
    key = name.removesuffix(".json")
    if key not in _SCHEMAS:
        raise HTTPException(status_code=404, detail=f"unknown schema: {name}")
    return load_schema(_SCHEMAS[key])


class ConfigPayload(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    godot_bin: str | None = None


def read_config(request: Request) -> dict[str, Any]:
    """Configuration with the API key represented as a boolean, never echoed."""
    settings = settings_for(request)
    return {
        "base_url": settings.llm.base_url,
        "model": settings.llm.model,
        "has_key": settings.llm_configured,
        "godot_bin": settings.godot_bin,
        "deploy_host": settings.deploy.host,
        "user_config": str(user_config_path()),
    }


@router.get("/config")
def get_config(request: Request) -> dict[str, Any]:
    return read_config(request)


@router.put("/config")
def put_config(request: Request, payload: ConfigPayload) -> dict[str, Any]:
    values: dict[str, str] = {}
    if payload.base_url:
        values["GAMELINK_LLM_BASE_URL"] = payload.base_url
    if payload.model:
        values["GAMELINK_LLM_MODEL"] = payload.model
    if payload.api_key:
        values["GAMELINK_LLM_API_KEY"] = payload.api_key
    if payload.godot_bin:
        values["GAMELINK_GODOT_BIN"] = payload.godot_bin
    if values:
        save_user_config(values)
    return read_config(request)
