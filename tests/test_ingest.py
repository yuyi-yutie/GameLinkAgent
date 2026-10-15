from pathlib import Path

import pytest

from gamelink.ingest import GodotProject, parse_godot_config

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "examples" / "snake-single"
MP_FIXTURE = REPO / "examples" / "snake-mp"


def test_parse_godot_config():
    cfg = parse_godot_config(
        '[application]\nconfig/name="X"\nrun/main_scene="res://a.tscn"\n'
        '[autoload]\nNetworkManager="*res://net.gd"\n'
    )
    assert cfg["application/config/name"] == '"X"'
    assert cfg["autoload/NetworkManager"] == '"*res://net.gd"'


def test_discover_fixture():
    project = GodotProject.discover(FIXTURE)
    assert project.name == "Snake Single"
    assert project.main_scene == "res://scenes/main.tscn"
    assert len(project.scripts) == 2
    assert len(project.scenes) == 1
    assert project.autoloads == {}


def test_summary_has_no_networking_yet():
    project = GodotProject.discover(FIXTURE)
    summary = project.summary()
    assert "snake" in summary.lower()
    assert "@rpc" not in summary


def test_discover_multiplayer_fixture():
    project = GodotProject.discover(MP_FIXTURE)
    assert project.name == "Snake MP"
    assert "NetworkManager" in project.autoloads
    assert len(project.scripts) == 3
    assert len(project.scenes) == 1


def test_missing_project_raises(tmp_path: Path):
    from gamelink.errors import IngestError

    with pytest.raises(IngestError):
        GodotProject.discover(tmp_path)
