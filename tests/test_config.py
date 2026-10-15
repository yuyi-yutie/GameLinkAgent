from gamelink.config import (
    DEFAULT_BASE_URL,
    Settings,
    load_user_config,
    save_user_config,
    user_config_path,
)


def _point_config_at(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("GAMELINK_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GAMELINK_LLM_BASE_URL", raising=False)


def test_user_config_roundtrip(tmp_path, monkeypatch):
    _point_config_at(tmp_path, monkeypatch)
    path = save_user_config({"GAMELINK_LLM_API_KEY": "abc"})
    assert path == user_config_path()
    assert path.is_file()
    assert load_user_config()["GAMELINK_LLM_API_KEY"] == "abc"


def test_user_config_overrides_dotenv(tmp_path, monkeypatch):
    _point_config_at(tmp_path, monkeypatch)
    save_user_config({"GAMELINK_LLM_API_KEY": "from-user"})
    env_file = tmp_path / ".env"
    env_file.write_text("GAMELINK_LLM_API_KEY=from-dotenv\n", encoding="utf-8")

    settings = Settings.load(env_file)
    assert settings.llm.api_key == "from-user"
    assert settings.llm_configured is True


def test_environment_variable_wins(tmp_path, monkeypatch):
    _point_config_at(tmp_path, monkeypatch)
    save_user_config({"GAMELINK_LLM_API_KEY": "from-user"})
    monkeypatch.setenv("GAMELINK_LLM_API_KEY", "from-env")

    settings = Settings.load(tmp_path / "missing.env")
    assert settings.llm.api_key == "from-env"


def test_empty_dotenv_key_is_not_treated_as_configured(tmp_path, monkeypatch):
    _point_config_at(tmp_path, monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("GAMELINK_LLM_API_KEY=\n", encoding="utf-8")

    settings = Settings.load(env_file)
    assert settings.llm.api_key is None
    assert settings.llm_configured is False
    assert settings.llm.base_url == DEFAULT_BASE_URL
