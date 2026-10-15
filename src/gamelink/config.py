"""Configuration resolution.

Precedence for every setting (highest first):

1. real environment variables
2. the per-user config file (written by the welcome screen / ``gla config``)
3. the repo-local ``.env`` file
4. built-in defaults

The LLM API key is expected to live in the **user** config file, not in the repo.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


def _read_dotenv(path: Path) -> dict[str, str]:
    """Parse a minimal ``.env`` file into a mapping (does not touch the environment)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def user_config_path() -> Path:
    """Location of the per-user config file."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "GameLinkAgent" / "config.json"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "gamelink" / "config.json"


def load_user_config() -> dict[str, str]:
    path = user_config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if value}


def save_user_config(values: dict[str, str]) -> Path:
    """Merge ``values`` into the user config file and return its path."""
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = load_user_config()
    merged.update({key: value for key, value in values.items() if value})
    path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


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

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm.api_key)

    @classmethod
    def load(cls, env_file: Path | None = None) -> Settings:
        file_values = _read_dotenv(env_file or Path.cwd() / ".env")
        user_values = load_user_config()

        def resolve(name: str, default: str = "") -> str:
            for source in (os.environ, user_values, file_values):
                value = source.get(name)
                if value:
                    return value
            return default

        llm = LLMSettings(
            base_url=resolve("GAMELINK_LLM_BASE_URL", DEFAULT_BASE_URL),
            api_key=resolve("GAMELINK_LLM_API_KEY") or None,
            model=resolve("GAMELINK_LLM_MODEL", DEFAULT_MODEL),
            temperature=float(resolve("GAMELINK_LLM_TEMPERATURE", "0")),
        )
        deploy = DeploySettings(
            host=resolve("GAMELINK_DEPLOY_HOST") or None,
            user=resolve("GAMELINK_DEPLOY_USER", "Administrator"),
            ssh_port=int(resolve("GAMELINK_DEPLOY_SSH_PORT", "22")),
            key_path=resolve("GAMELINK_DEPLOY_KEY") or None,
            remote_dir=resolve("GAMELINK_DEPLOY_REMOTE_DIR", "C:/GameLink/server"),
            game_port=int(resolve("GAMELINK_DEPLOY_GAME_PORT", "7000")),
        )
        return cls(llm=llm, deploy=deploy, godot_bin=resolve("GAMELINK_GODOT_BIN") or None)
