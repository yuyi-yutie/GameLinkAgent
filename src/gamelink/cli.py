"""GameLink Agent command-line interface."""

from __future__ import annotations

import platform
import shlex
import sys
import time
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from typer.main import get_command

from gamelink import __version__, ui
from gamelink.analyze import Analyzer
from gamelink.analyze.llm import REASONING
from gamelink.config import Settings, user_config_path
from gamelink.deploy import build_deploy_plan, package
from gamelink.errors import GameLinkError
from gamelink.generate import generate_server
from gamelink.ingest import GodotProject
from gamelink.options import OPTION_CHOICES, DesignerOptions
from gamelink.spec import load_yaml, read_specs, verify_consistency, write_specs
from gamelink.spec.io import dump_yaml
from gamelink.util import slugify


def _configure_output() -> None:
    """Keep the console's native encoding (so CJK renders correctly) but never
    crash on characters it cannot encode (e.g. emoji coming back from the LLM)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


_configure_output()

app = typer.Typer(
    name="gla",
    help="GameLink Agent — 网络语义驱动的游戏服务端自动生成与部署智能体"
    "（不带参数运行会进入交互式欢迎界面）",
    invoke_without_command=True,
)
console = Console()

OPTIONS_FILE = "gamelink.options.yaml"


def _fail(exc: GameLinkError) -> NoReturn:
    console.print(f"[red]error:[/red] {exc}")
    raise typer.Exit(code=1)


def _split_args(line: str) -> list[str]:
    tokens = shlex.split(line, posix=False)
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] == '"' else t for t in tokens]


def _write_report(out_dir: Path, project_name: str, report: str) -> Path:
    """Write the analysis report as Markdown and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slugify(project_name)}-report.md"
    path.write_text((report or "(无报告)").rstrip() + "\n", encoding="utf-8")
    return path


def _welcome_shell() -> None:
    """Interactive welcome screen: lists commands, ensures the LLM is configured."""
    settings = Settings.load()
    ui.render_welcome(console, settings)
    if not settings.llm_configured:
        console.print("[yellow]尚未配置 LLM API key，先配置一下：[/yellow]")
        ui.configure_llm(console)
        console.print()

    command = get_command(app)
    while True:
        try:
            line = Prompt.ask("[bold cyan]gla[/bold cyan]", default="", show_default=False)
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        line = (line or "").strip()
        if not line:
            continue

        parts = _split_args(line)
        head = parts[0].lower()
        if head in ("exit", "quit", ":q"):
            break
        if head == "help":
            if len(parts) > 1:
                ui.render_command_help(console, parts[1])
            else:
                ui.render_welcome(console, Settings.load(), show_status=False)
            continue
        if head in ("?", "-h", "--help"):
            ui.render_welcome(console, Settings.load(), show_status=False)
            continue

        try:
            command.main(parts, prog_name="gla", standalone_mode=False)
        except typer.Exit:
            pass
        except typer.Abort:
            console.print()
        except (EOFError, KeyboardInterrupt):
            console.print()
        except SystemExit:
            pass
        except Exception as exc:  # keep the shell alive no matter what
            console.print(f"[red]错误：[/red]{exc}")
    console.print("[dim]已退出。[/dim]")


@app.callback(invoke_without_command=True)
def _entry(ctx: typer.Context) -> None:
    """不带参数运行时进入欢迎界面。"""
    if ctx.invoked_subcommand is not None:
        return
    if not sys.stdin.isatty():
        console.print(ctx.get_help())
        return
    _welcome_shell()


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
    """显示版本。"""
    console.print(f"gamelink-agent {__version__}")


@app.command()
def config() -> None:
    """配置 LLM（API key / 端点 / 模型），保存到用户目录。"""
    ui.configure_llm(console)


@app.command("help")
def help_command(command_name: str | None = typer.Argument(None)) -> None:
    """查看命令列表，或某个命令的详细用法（例如 `gla help analyze`）。"""
    if command_name:
        ui.render_command_help(console, command_name)
    else:
        ui.render_welcome(console, Settings.load())


@app.command()
def shell() -> None:
    """进入交互式欢迎界面（等价于不带参数运行 gla）。"""
    _welcome_shell()


@app.command()
def doctor() -> None:
    """检查环境（Python / Godot / LLM / 部署 / 用户配置）。"""
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
    table.add_row(
        "user config",
        "ok" if user_config_path().is_file() else "warn",
        str(user_config_path()),
    )
    console.print(table)


@app.command()
def inspect(project: Path = typer.Argument(..., exists=True, help="Godot project directory")) -> None:
    """解析 Godot 工程结构并打印摘要。"""
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
    out: Path = typer.Option(Path("specs"), "--out", help="Directory to write the report into"),
    emit_specs: bool = typer.Option(
        False, "--specs", help="同时写出规格文件（供 generate / verify 使用）"
    ),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Prompt for options"),
    authority_model: str = typer.Option("server_authoritative", "--authority-model"),
    sync_mechanism: str = typer.Option("state+event", "--sync-mechanism"),
    transport: str = typer.Option("enet", "--transport"),
    room_mode: str = typer.Option("single", "--room-mode"),
    max_players: int = typer.Option(4, "--max-players"),
    tick_rate: int = typer.Option(15, "--tick-rate"),
    persistence: str = typer.Option("none", "--persistence"),
    deploy_target: str = typer.Option("windows_server", "--deploy-target"),
    raw_stream: bool = typer.Option(
        False, "--stream", help="实时打印 LLM 原始输出（含推理过程）"
    ),
) -> None:
    """LLM 分析工程，输出中文 Markdown 报告（加 --specs 可导出规格）。"""
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

    thought = 0
    received = 0
    json_announced = False
    started = time.monotonic()

    status = None
    if not raw_stream:
        if console.is_terminal:
            status = console.status("正在调用 LLM 分析工程…", spinner="dots")
            status.start()
        else:
            console.print("正在调用 LLM 分析工程…")

    def on_chunk(kind: str, text: str) -> None:
        nonlocal thought, received, json_announced
        if kind == REASONING:
            thought += len(text)
            if raw_stream:
                # Write straight to stdout so the model's own newlines survive and
                # the terminal wraps at its own width (rich would collapse them).
                sys.stdout.write(text)
                sys.stdout.flush()
            elif status is not None:
                status.update(f"正在调用 LLM 分析工程… 模型已推理 {thought:,} 字符")
            return
        received += len(text)
        if raw_stream:
            if not json_announced:
                json_announced = True
                sys.stdout.write("\n\n[ 推理结束，正在生成结构化结果（内容见下方报告）… ]\n")
                sys.stdout.flush()
        elif status is not None:
            status.update(f"正在生成结构化结果… 已接收 {received:,} 字符")

    result = None
    report_path: Path | None = None
    spec_paths: list[Path] = []
    error: GameLinkError | None = None
    try:
        result = Analyzer(settings).analyze(proj, options, on_chunk=on_chunk)
        report_path = _write_report(out, proj.name, result.report)
        if emit_specs:
            protocol_path, arch_path = write_specs(
                result.protocol_spec, result.architecture_spec, out
            )
            dump_yaml(options.to_dict(), out / OPTIONS_FILE)
            spec_paths = [protocol_path, arch_path]
    except GameLinkError as exc:
        error = exc
    finally:
        if status is not None:
            status.stop()
        if raw_stream:
            console.print()
    if error is not None:
        _fail(error)

    console.print(f"[dim]分析完成，用时 {time.monotonic() - started:.1f}s[/dim]")
    console.rule("[bold]分析报告")
    console.print(result.report or "(无报告)")
    console.rule("输出文件")
    console.print(f"  [green]{report_path}[/green]")
    for path in spec_paths:
        console.print(f"  {path}")
    if not emit_specs:
        console.print("[dim]（如需生成服务端：加 --specs 一并导出规格，再执行 `gla generate`）[/dim]")


@app.command()
def generate(
    project: Path = typer.Argument(..., exists=True, help="Godot project directory"),
    specs: Path = typer.Option(Path("specs"), "--specs", help="Directory containing the specs"),
    out: Path = typer.Option(Path("out/server"), "--out", help="Output server project directory"),
) -> None:
    """按规格生成可运行的 Godot 服务端工程。"""
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
    """用 Godot 内省校验规格与实现是否一致。"""
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
    server_dir: Path = typer.Argument(..., exists=True, help="生成的 Godot 服务端工程目录"),
    out: Path | None = typer.Option(None, "--out", help="导出目录（默认 <工程>/dist）"),
) -> None:
    """导出 headless 服务端，并生成部署说明（一键部署包）。"""
    settings = Settings.load()
    plan = build_deploy_plan(server_dir, settings, DesignerOptions(), out_dir=out)
    console.print("[bold]一键部署：导出 headless 服务端[/bold]")
    console.print(plan.describe())
    console.print()
    try:
        with console.status("正在导出 Godot 服务端（首次导出较慢）…", spinner="dots"):
            result = package(plan, settings.godot_bin)
    except GameLinkError as exc:
        _fail(exc)
    console.print(f"[green]完成[/green]：{len(result.files)} 个文件 -> {result.dist_dir}")
    for path in result.files:
        console.print(f"  {path}")
    console.print("\n[dim]把 dist 整个目录上传到服务器，按 `使用说明.md` 操作即可。[/dim]")


if __name__ == "__main__":
    app()
