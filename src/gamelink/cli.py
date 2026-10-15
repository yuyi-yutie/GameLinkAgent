"""GameLink Agent command-line interface."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console
from rich.table import Table

from gamelink import __version__
from gamelink.analyze import Analyzer
from gamelink.config import Settings
from gamelink.deploy import build_deploy_plan
from gamelink.deploy import deploy as run_deploy
from gamelink.errors import GameLinkError
from gamelink.generate import generate_server
from gamelink.ingest import GodotProject
from gamelink.options import OPTION_CHOICES, DesignerOptions
from gamelink.spec import load_yaml, read_specs, verify_consistency, write_specs
from gamelink.spec.io import dump_yaml

app = typer.Typer(
    help="GameLink Agent — 网络语义驱动的游戏服务端自动生成与部署智能体",
    no_args_is_help=True,
)
console = Console()

OPTIONS_FILE = "gamelink.options.yaml"


def _fail(exc: GameLinkError) -> NoReturn:
    console.print(f"[red]error:[/red] {exc}")
    raise typer.Exit(code=1)


def _choose(name: str, choices: list[str], default: str) -> str:
    console.print(f"  [cyan]{name}[/cyan]: {', '.join(choices)}")
    value = typer.prompt(f"  {name}", default=default)
    while value not in choices:
        console.print(f"  [yellow]invalid — choose one of {choices}[/yellow]")
        value = typer.prompt(f"  {name}", default=default)
    return value


def _interactive_options(default: DesignerOptions) -> DesignerOptions:
    console.print("[bold]Configure server generation[/bold]")
    return DesignerOptions(
        authority_model=_choose("authority_model", OPTION_CHOICES["authority_model"], default.authority_model),
        sync_mechanism=_choose("sync_mechanism", OPTION_CHOICES["sync_mechanism"], default.sync_mechanism),
        transport=_choose("transport", OPTION_CHOICES["transport"], default.transport),
        room_mode=_choose("room_mode", OPTION_CHOICES["room_mode"], default.room_mode),
        max_players=typer.prompt("  max_players", default=default.max_players, type=int),
        tick_rate=typer.prompt("  tick_rate", default=default.tick_rate, type=int),
        persistence=_choose("persistence", OPTION_CHOICES["persistence"], default.persistence),
        deploy_target=_choose("deploy_target", OPTION_CHOICES["deploy_target"], default.deploy_target),
    )


@app.command()
def version() -> None:
    """Print the GameLink Agent version."""
    console.print(f"gamelink-agent {__version__}")


@app.command()
def doctor() -> None:
    """Check the environment: Python, Godot, LLM config and deploy target."""
    settings = Settings.load()
    godot_ok = bool(settings.godot_bin) and Path(settings.godot_bin).exists()
    table = Table("check", "status", "detail")
    table.add_row("python", "ok", platform.python_version())
    table.add_row(
        "godot",
        "ok" if godot_ok else "warn",
        settings.godot_bin or "GAMELINK_GODOT_BIN not set (verification & export disabled)",
    )
    table.add_row(
        "llm",
        "ok" if settings.llm.api_key else "warn",
        f"{settings.llm.model} @ {settings.llm.base_url}",
    )
    table.add_row(
        "deploy",
        "ok" if settings.deploy.host else "warn",
        settings.deploy.host or "GAMELINK_DEPLOY_HOST not set",
    )
    console.print(table)


@app.command()
def inspect(project: Path = typer.Argument(..., exists=True, help="Godot project directory")) -> None:
    """Ingest a Godot project and print a summary."""
    try:
        proj = GodotProject.discover(project)
    except GameLinkError as exc:
        _fail(exc)
    console.print(f"[bold]{proj.name}[/bold]  ({proj.root})")
    console.print(f"  features:   {', '.join(proj.features) or '-'}")
    console.print(f"  main scene: {proj.main_scene or '-'}")
    console.print(f"  autoloads:  {', '.join(proj.autoloads) or '-'}")
    console.print(
        f"  files:      {len(proj.scripts)} scripts, {len(proj.scenes)} scenes, "
        f"{len(proj.resources)} resources"
    )


@app.command()
def analyze(
    project: Path = typer.Argument(..., exists=True, help="Godot project directory"),
    out: Path = typer.Option(Path("specs"), "--out", help="Directory to write specs into"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for options"),
    authority_model: str = typer.Option("server_authoritative", "--authority-model"),
    sync_mechanism: str = typer.Option("state+event", "--sync-mechanism"),
    transport: str = typer.Option("enet", "--transport"),
    room_mode: str = typer.Option("single", "--room-mode"),
    max_players: int = typer.Option(4, "--max-players"),
    tick_rate: int = typer.Option(15, "--tick-rate"),
    persistence: str = typer.Option("none", "--persistence"),
    deploy_target: str = typer.Option("windows_server", "--deploy-target"),
) -> None:
    """Analyze a project and generate the two specs."""
    try:
        proj = GodotProject.discover(project)
    except GameLinkError as exc:
        _fail(exc)

    options = DesignerOptions(
        authority_model=authority_model,
        sync_mechanism=sync_mechanism,
        transport=transport,
        room_mode=room_mode,
        max_players=max_players,
        tick_rate=tick_rate,
        persistence=persistence,
        deploy_target=deploy_target,
    )
    if interactive:
        options = _interactive_options(options)

    settings = Settings.load()
    try:
        result = Analyzer(settings).analyze(proj, options)
        protocol_path, arch_path = write_specs(result.protocol_spec, result.architecture_spec, out)
        dump_yaml(options.to_dict(), out / OPTIONS_FILE)
    except GameLinkError as exc:
        _fail(exc)

    console.rule("[bold]Analysis report")
    console.print(result.report or "(no report)")
    console.rule("Specs")
    console.print(f"  {protocol_path}")
    console.print(f"  {arch_path}")

    issues = verify_consistency(proj.root, result.protocol_spec, result.architecture_spec, settings.godot_bin)
    console.rule("Consistency check")
    for issue in issues:
        color = {"error": "red", "warning": "yellow", "info": "green"}[issue.severity]
        console.print(f"  [{color}]{issue.severity}[/{color}] {issue.message}")


@app.command()
def generate(
    project: Path = typer.Argument(..., exists=True, help="Godot project directory"),
    specs: Path = typer.Option(Path("specs"), "--specs", help="Directory containing the specs"),
    out: Path = typer.Option(Path("out/server"), "--out", help="Output server project directory"),
) -> None:
    """Generate a Godot server project from specs."""
    try:
        proj = GodotProject.discover(project)
        protocol, architecture = read_specs(specs)
    except GameLinkError as exc:
        _fail(exc)

    options_path = specs / OPTIONS_FILE
    options = DesignerOptions.from_dict(load_yaml(options_path)) if options_path.exists() else DesignerOptions()

    try:
        result = generate_server(proj, options, protocol, architecture, out)
    except GameLinkError as exc:
        _fail(exc)

    console.print(f"[green]generated[/green] {len(result.files)} files into {result.out_dir}")
    for path in result.files:
        console.print(f"  {path.relative_to(result.out_dir)}")
    if result.todos:
        console.rule("Manual work required")
        for todo in result.todos:
            console.print(f"  [yellow]TODO[/yellow] {todo}")


@app.command()
def verify(
    project: Path = typer.Argument(..., exists=True, help="Godot project directory"),
    specs: Path = typer.Option(Path("specs"), "--specs", help="Directory containing the specs"),
) -> None:
    """Check specs against the engine's ground truth (Godot introspection)."""
    try:
        protocol, architecture = read_specs(specs)
    except GameLinkError as exc:
        _fail(exc)

    settings = Settings.load()
    issues = verify_consistency(project, protocol, architecture, settings.godot_bin)
    for issue in issues:
        color = {"error": "red", "warning": "yellow", "info": "green"}[issue.severity]
        console.print(f"  [{color}]{issue.severity}[/{color}] {issue.message}")


@app.command()
def deploy(
    server_dir: Path = typer.Argument(..., exists=True, help="Generated server project directory"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Preview (default) or apply"),
) -> None:
    """Deploy a generated server to the Windows cloud server."""
    settings = Settings.load()
    plan = build_deploy_plan(server_dir, settings, DesignerOptions(), dry_run=dry_run)
    try:
        result = run_deploy(plan)
    except GameLinkError as exc:
        _fail(exc)
    console.print(result.detail)
    if result.connect_address:
        console.print(f"connect at [bold]{result.connect_address}[/bold]")


if __name__ == "__main__":
    app()
