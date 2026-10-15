from pathlib import Path

from typer.testing import CliRunner

from gamelink.cli import app

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "examples" / "snake-single"
SPECS = REPO / "examples" / "snake-specs"

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "gamelink-agent" in result.stdout


def test_inspect():
    result = runner.invoke(app, ["inspect", str(FIXTURE)])
    assert result.exit_code == 0, result.stdout
    assert "Snake" in result.stdout


def test_generate_from_example_specs(tmp_path):
    out = tmp_path / "server"
    result = runner.invoke(
        app,
        ["generate", str(FIXTURE), "--specs", str(SPECS), "--out", str(out)],
    )
    assert result.exit_code == 0, result.stdout

    network_manager = out / "scripts" / "network_manager.gd"
    main = out / "scripts" / "main.gd"
    snake = out / "scripts" / "snake.gd"
    assert network_manager.exists()
    assert main.exists()
    assert snake.exists()

    nm_text = network_manager.read_text(encoding="utf-8")
    main_text = main.read_text(encoding="utf-8")
    assert "ENetMultiplayerPeer" in nm_text
    assert "{{" not in nm_text  # all template placeholders were substituted
    assert "{{" not in main_text
    assert "submit_direction" in main_text  # RPC name comes from the spec
    assert "[autoload]" in (out / "project.godot").read_text(encoding="utf-8")
    assert (out / "gamelink" / "protocol.spec.yaml").exists()


def test_deploy_dry_run(tmp_path):
    server = tmp_path / "server"
    server.mkdir()
    result = runner.invoke(app, ["deploy", str(server), "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert "dry-run" in result.stdout


def test_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "python" in result.stdout
