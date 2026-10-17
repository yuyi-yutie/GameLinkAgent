"""GameLink Agent command-line interface."""

from __future__ import annotations

import platform
import shlex
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.status import Status
from rich.table import Table
from rich.text import Text
from typer.main import get_command

from gamelink import __version__, ui
from gamelink.analyze.llm import REASONING
from gamelink.config import Settings, user_config_path
from gamelink.errors import GameLinkError
from gamelink.options import OPTION_CHOICES, DesignerOptions
from gamelink.pipeline import (
    CHUNK,
    ISSUE,
    LOG,
    PROGRESS,
    Emitter,
    Event,
    analyze_project,
    deploy_server,
    generate_from_specs,
    inspect_project,
    verify_project,
)


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


def _fail(exc: GameLinkError) -> NoReturn:
    console.print(f"[red]error:[/red] {exc}")
    raise typer.Exit(code=1)


def _split_args(line: str) -> list[str]:
    tokens = shlex.split(line, posix=False)
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] == '"' else t for t in tokens]


class _ConsoleRenderer:
    """Renders pipeline events with Rich.

    This holds the progress UI the CLI used to keep inline: a live spinner while a
    long stage runs, the raw model stream under ``--stream``, and log/issue lines
    as they arrive. The pipeline itself stays presentation-free.
    """

    def __init__(self, console: Console, *, raw_stream: bool = False) -> None:
        self.console = console
        self.raw_stream = raw_stream
        self.status: Status | None = None
        self.message: str | None = None
        self.thought = 0
        self.received = 0
        self.announced = False

    def __call__(self, event: Event) -> None:
        if event.type == PROGRESS:
            self._progress(str(event.data.get("message", "")))
        elif event.type == CHUNK:
            self._chunk(str(event.data.get("kind", "")), str(event.data.get("text", "")))
        elif event.type == LOG:
            self._log(event.data)
        elif event.type == ISSUE:
            self._issue(event.data)

    def close(self) -> None:
        if self.status is not None:
            self.status.stop()
            self.status = None
        if self.raw_stream:
            self.console.print()

    def _progress(self, message: str) -> None:
        if self.raw_stream or not message:
            return
        if self.console.is_terminal:
            if self.status is None:
                self.status = self.console.status(message, spinner="dots")
                self.status.start()
            elif message != self.message:
                self.status.update(message)
        elif message != self.message:
            self.console.print(message)
        self.message = message

    def _chunk(self, kind: str, text: str) -> None:
        if kind == REASONING:
            self.thought += len(text)
            if self.raw_stream:
                # Straight to stdout so the model's own newlines survive and the
                # terminal wraps at its own width (rich would collapse them).
                sys.stdout.write(text)
                sys.stdout.flush()
            elif self.status is not None:
                self.status.update(f"正在调用 LLM 分析工程… 模型已推理 {self.thought:,} 字符")
            return
        self.received += len(text)
        if self.raw_stream:
            if not self.announced:
                self.announced = True
                sys.stdout.write("\n\n[ 推理结束，正在生成结构化结果（内容见下方报告）… ]\n")
                sys.stdout.flush()
        elif self.status is not None:
            self.status.update(f"正在生成结构化结果… 已接收 {self.received:,} 字符")

    def _log(self, data: dict[str, Any]) -> None:
        message = str(data.get("message", ""))
        level = str(data.get("level", "info"))
        if level == "title":
            self.console.print(f"[bold]{message}[/bold]")
        elif level in ("warn", "error"):
            color = "yellow" if level == "warn" else "red"
            self.console.print(f"[{color}]{message}[/{color}]")
        else:
            self.console.print(message, markup=False, highlight=False)

    def _issue(self, data: dict[str, Any]) -> None:
        severity = str(data.get("severity", "info"))
        color = {"error": "red", "warning": "yellow", "info": "green"}.get(severity, "white")
        line = Text("  ")
        line.append(severity, style=color)
        line.append(f" {data.get('message', '')}")
        self.console.print(line)


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
    """配置 LLM（API key / 端点 / 模型）或 Godot 引擎路径，保存到用户目录。"""
    ui.configure(console)


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
def web(
    workspace: Path = typer.Option(Path("."), "--workspace", help="工作区目录（默认当前目录）"),
    port: int = typer.Option(8765, "--port", help="监听端口"),
    no_browser: bool = typer.Option(False, "--no-browser", help="不自动打开浏览器"),
) -> None:
    """启动本地 Web 界面（浏览器打开 http://127.0.0.1:<端口>）。"""
    try:
        from gamelink.web import serve
    except ImportError as exc:
        console.print(
            "[yellow]Web 界面需要额外的依赖，请先安装：[/yellow]\n"
            '  pip install -e ".[web]"'
        )
        raise typer.Exit(code=1) from exc

    console.print(f"[bold]GameLink Agent[/bold] Web 界面 → http://127.0.0.1:{port}/")
    console.print(f"[dim]工作区：{workspace.resolve()}[/dim]")
    console.print("[dim]按 Ctrl+C 停止。[/dim]")
    try:
        serve(workspace, port=port, open_browser=not no_browser)
    except KeyboardInterrupt:
        console.print("\n[dim]已停止。[/dim]")


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
        proj = inspect_project(project)
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
    renderer = _ConsoleRenderer(console, raw_stream=raw_stream)
    started = time.monotonic()
    try:
        outcome = analyze_project(
            inspect_project(project),
            options,
            settings,
            Emitter(renderer),
            out_dir=out,
            emit_specs=emit_specs,
        )
    except GameLinkError as exc:
        _fail(exc)
    finally:
        renderer.close()

    console.print(f"[dim]分析完成，用时 {time.monotonic() - started:.1f}s[/dim]")
    console.rule("[bold]分析报告")
    console.print(outcome.report or "(无报告)")
    console.rule("输出文件")
    console.print(f"  [green]{outcome.report_path}[/green]")
    for path in outcome.spec_paths:
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
    renderer = _ConsoleRenderer(console)
    try:
        result = generate_from_specs(
            inspect_project(project), specs, out, Emitter(renderer)
        )
    except GameLinkError as exc:
        _fail(exc)
    finally:
        renderer.close()

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
    renderer = _ConsoleRenderer(console)
    try:
        verify_project(project, specs, Settings.load(), Emitter(renderer))
    except GameLinkError as exc:
        _fail(exc)
    finally:
        renderer.close()


@app.command()
def deploy(
    server_dir: Path = typer.Argument(..., exists=True, help="生成的 Godot 服务端工程目录"),
    out: Path | None = typer.Option(None, "--out", help="导出目录（默认 <工程>/dist）"),
) -> None:
    """导出 headless 服务端，并生成部署说明（一键部署包）。"""
    renderer = _ConsoleRenderer(console)
    try:
        outcome = deploy_server(server_dir, Settings.load(), Emitter(renderer), out_dir=out)
    except GameLinkError as exc:
        _fail(exc)
    finally:
        renderer.close()

    result = outcome.result
    console.print(f"[green]完成[/green]：{len(result.files)} 个文件 -> {result.dist_dir}")
    for path in result.files:
        console.print(f"  {path}")
    console.print("\n[dim]把 dist 整个目录上传到服务器，按 `使用说明.md` 操作即可。[/dim]")


if __name__ == "__main__":
    app()
