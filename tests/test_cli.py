import json
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

    # Deployment artifacts: an export preset and a manifest for `deploy`.
    assert (out / "export_presets.cfg").exists()
    manifest = json.loads((out / "gamelink" / "server.json").read_text(encoding="utf-8"))
    assert manifest["exe_name"].endswith("-server.exe")
    assert manifest["preset"]


def test_write_report_uses_project_slug(tmp_path):
    from gamelink.pipeline import write_report

    path = write_report(tmp_path, "Snake Single", "# 分析\n\n正文")
    assert path.name == "snake-single-report.md"
    assert path.read_text(encoding="utf-8").startswith("# 分析")


def test_deploy_plan_reads_manifest(tmp_path):
    from gamelink.config import Settings
    from gamelink.deploy import build_deploy_plan
    from gamelink.options import DesignerOptions

    server = tmp_path / "server"
    (server / "gamelink").mkdir(parents=True)
    (server / "gamelink" / "server.json").write_text(
        json.dumps(
            {
                "game": "Snake Single",
                "slug": "snake-single",
                "exe_name": "snake-single-server.exe",
                "service_name": "snake-single-server",
                "port": 7000,
                "max_players": 4,
            }
        ),
        encoding="utf-8",
    )
    plan = build_deploy_plan(server, Settings.load(tmp_path / "none.env"), DesignerOptions())
    assert plan.exe_name == "snake-single-server.exe"
    assert plan.port == 7000
    assert plan.max_players == 4
    assert plan.dist_dir == server / "dist"


def test_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "python" in result.stdout


def test_help_lists_commands_and_shows_detail():
    listing = runner.invoke(app, ["help"])
    assert listing.exit_code == 0, listing.stdout
    assert "analyze" in listing.stdout

    detail = runner.invoke(app, ["help", "analyze"])
    assert detail.exit_code == 0, detail.stdout
    assert "用法" in detail.stdout
    assert "--specs" in detail.stdout


def test_render_command_help_unknown_returns_false():
    from rich.console import Console

    from gamelink import ui

    assert ui.render_command_help(Console(), "definitely-not-a-command") is False


def test_command_docs_are_consistent():
    from gamelink import ui

    names = [doc.name for doc in ui.COMMANDS]
    assert len(names) == len(set(names)), "command names must be unique"
    assert all(doc.group in ui.GROUPS for doc in ui.COMMANDS)


def test_godot_candidate_selection(tmp_path):
    from gamelink import ui

    for name in (
        "Godot_v4.7.2-stable_win64.exe",
        "Godot_v4.7.2-stable_win64_console.exe",
        "unrelated.exe",
        "notes.txt",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")

    candidates = ui._godot_candidates(tmp_path)
    assert len(candidates) == 3
    assert all(path.suffix == ".exe" for path in candidates)
    assert max(candidates, key=ui._godot_rank).name == "Godot_v4.7.2-stable_win64_console.exe"


def test_godot_candidates_accepts_a_file(tmp_path):
    from gamelink import ui

    exe = tmp_path / "godot.exe"
    exe.write_text("x", encoding="utf-8")
    assert ui._godot_candidates(exe) == [exe]


def test_godot_candidates_empty_folder(tmp_path):
    from gamelink import ui

    assert ui._godot_candidates(tmp_path) == []
