"""Configuration loading from environment variables and an optional ``.env`` file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal ``.env`` loader (no external dependency).

    Existing environment variables always win, so real env config overrides the file.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    api_key: str | None
    model: str
    temperature: float


@dataclass(frozen=True)
class DeploySettings:
    host: str | None
    user: str
    ssh_port: int
    key_path: str | None
    remote_dir: str
    game_port: int


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration."""

    llm: LLMSettings
    deploy: DeploySettings
    godot_bin: str | None

    @classmethod
    def load(cls, env_file: Path | None = None) -> Settings:
        if env_file is not None:
            _load_dotenv(env_file)
        else:
            _load_dotenv(Path.cwd() / ".env")

        llm = LLMSettings(
            base_url=os.environ.get("GAMELINK_LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.environ.get("GAMELINK_LLM_API_KEY") or None,
            model=os.environ.get("GAMELINK_LLM_MODEL", "gpt-4o-mini"),
            temperature=float(os.environ.get("GAMELINK_LLM_TEMPERATURE", "0")),
        )
        deploy = DeploySettings(
            host=os.environ.get("GAMELINK_DEPLOY_HOST") or None,
            user=os.environ.get("GAMELINK_DEPLOY_USER", "Administrator"),
            ssh_port=int(os.environ.get("GAMELINK_DEPLOY_SSH_PORT", "22")),
            key_path=os.environ.get("GAMELINK_DEPLOY_KEY") or None,
            remote_dir=os.environ.get("GAMELINK_DEPLOY_REMOTE_DIR", "C:/GameLink/server"),
            game_port=int(os.environ.get("GAMELINK_DEPLOY_GAME_PORT", "7000")),
        )
        return cls(llm=llm, deploy=deploy, godot_bin=os.environ.get("GAMELINK_GODOT_BIN") or None)
