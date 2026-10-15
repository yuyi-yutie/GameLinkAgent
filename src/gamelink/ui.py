"""Terminal UI: the welcome screen and the command reference.

Command metadata lives here (one place) and feeds both the welcome screen and
`help <command>`, so the CLI stays in sync with what it advertises.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from gamelink import __version__
from gamelink.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    Settings,
    save_user_config,
    user_config_path,
)


@dataclass(frozen=True)
class CommandDoc:
    name: str
    group: str
    summary: str
    usage: str
    notes: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()


GROUPS: tuple[str, ...] = ("分析", "生成与部署", "配置与工具")

COMMANDS: tuple[CommandDoc, ...] = (
    CommandDoc(
        name="inspect",
        group="分析",
        summary="解析 Godot 工程结构并打印摘要",
        usage="gla inspect <工程目录>",
        notes=(
            "显示工程名、主场景、autoload，以及脚本 / 场景 / 资源数量。",
            "不调用 LLM，无需 API key。",
        ),
        examples=("gla inspect examples/snake-single",),
    ),
    CommandDoc(
        name="analyze",
        group="分析",
        summary="LLM 分析工程 → 中文 Markdown 报告（可选导出规格）",
        usage="gla analyze <工程目录> [选项]",
        notes=(
            "默认只产出 Markdown 报告：specs/<工程名>-report.md。",
            "加 --specs 额外导出 protocol.spec.yaml / server-architecture.spec.yaml（供 generate 使用）。",
            "加 -i 交互式选择生成选项；加 --stream 实时打印模型的推理过程。",
            "需要先配置 LLM API key（见 `gla config`）。",
        ),
        examples=(
            "gla analyze examples/snake-single",
            "gla analyze examples/snake-single --specs",
            "gla analyze examples/snake-single -i --stream",
        ),
    ),
    CommandDoc(
        name="generate",
        group="生成与部署",
        summary="按规格生成可运行的 Godot 服务端工程",
        usage="gla generate <工程目录> --specs <规格目录> [--out <输出目录>]",
        notes=(
            "复制输入工程（保留资源与场景），写入网络层并给 project.godot 补上 autoload。",
            "RPC 函数名取自 protocol.spec 里的 message.id。",
            "同时写出 export_presets.cfg 与 gamelink/server.json（供 deploy 使用）。",
            "会打印需要人工/后续 LLM 补全的 refactors TODO 清单。",
        ),
        examples=("gla generate examples/snake-single --specs specs --out out/snake-gen",),
    ),
    CommandDoc(
        name="verify",
        group="生成与部署",
        summary="用 Godot 内省校验规格与实现是否一致",
        usage="gla verify <工程目录> --specs <规格目录>",
        notes=(
            "用 headless Godot 内省出真实的 @rpc 方法与 autoload，再与规格逐条比对。",
            "会报告两类差异：规格里有但工程里没有（疑似幻觉）、工程里有但规格漏了（遗漏）。",
            "需要配置 GAMELINK_GODOT_BIN。",
        ),
        examples=("gla verify examples/snake-mp --specs specs",),
    ),
    CommandDoc(
        name="deploy",
        group="生成与部署",
        summary="导出 headless 服务端 + 部署说明（一键部署包）",
        usage="gla deploy <生成的工程目录> [--out <导出目录>]",
        notes=(
            "用 Godot CLI 导出单文件 Windows x86_64 服务端（内嵌资源）。",
            "产出 <工程>/dist/：<slug>-server.exe、使用说明.md、scripts/*.ps1。",
            "不触碰任何远端服务器；把 dist 上传服务器后按 使用说明.md 操作即可。",
            "需要 Godot 引擎与已安装的导出模板。",
        ),
        examples=("gla deploy out/snake-gen",),
    ),
    CommandDoc(
        name="config",
        group="配置与工具",
        summary="配置 LLM（API key / 端点 / 模型）",
        usage="gla config",
        notes=(
            "保存到用户目录，不写入仓库：",
            "Windows: %APPDATA%\\GameLinkAgent\\config.json",
            "其他:    ~/.config/gamelink/config.json",
            "优先级：环境变量 > 用户配置 > 仓库 .env > 内置默认。",
        ),
        examples=("gla config",),
    ),
    CommandDoc(
        name="doctor",
        group="配置与工具",
        summary="检查环境（Python / Godot / LLM / 部署 / 用户配置）",
        usage="gla doctor",
        examples=("gla doctor",),
    ),
    CommandDoc(
        name="shell",
        group="配置与工具",
        summary="进入交互式欢迎界面（等价于不带参数运行 gla）",
        usage="gla shell",
    ),
    CommandDoc(
        name="help",
        group="配置与工具",
        summary="查看命令列表，或某个命令的详细用法",
        usage="gla help [命令名]",
        examples=("gla help analyze",),
    ),
    CommandDoc(
        name="version",
        group="配置与工具",
        summary="显示版本",
        usage="gla version",
    ),
    CommandDoc(
        name="exit",
        group="配置与工具",
        summary="退出交互界面",
        usage="exit",
    ),
)


def banner() -> Panel:
    return Panel.fit(
        f"[bold]GameLink Agent[/bold]  v{__version__}\n"
        "网络语义驱动的游戏服务端自动生成与部署智能体",
        border_style="cyan",
    )


def _status_line(console: Console, settings: Settings) -> None:
    llm = settings.llm
    llm_ok = bool(llm.api_key)
    godot_ok = bool(settings.godot_bin) and Path(settings.godot_bin).exists()
    console.print(
        "  "
        + f"LLM [{'green' if llm_ok else 'yellow'}]{'ok' if llm_ok else 'warn'}[/] ({llm.model})"
        + "   "
        + f"Godot [{'green' if godot_ok else 'yellow'}]{'ok' if godot_ok else 'warn'}[/]"
    )
    console.print(f"  配置 [dim]{user_config_path()}[/dim]")
    if not llm_ok:
        console.print("  [yellow]尚未配置 LLM API key —— 输入 `config` 配置。[/yellow]")
    console.print()


def render_welcome(console: Console, settings: Settings, *, show_status: bool = True) -> None:
    """Print the banner + grouped command list (the welcome screen)."""
    console.print(banner())
    if show_status:
        _status_line(console, settings)
    for group in GROUPS:
        docs = [doc for doc in COMMANDS if doc.group == group]
        if not docs:
            continue
        console.print(f"[bold]{group}[/bold]")
        for doc in docs:
            console.print(f"  [cyan]{doc.name:<18}[/cyan] {doc.summary}")
        console.print()
    console.print(
        "[dim]直接输入命令即可执行；`help <命令>` 看详细用法，"
        "`gla <命令> --help` 看全部选项，`exit` 退出。[/dim]"
    )


def render_command_help(console: Console, name: str) -> bool:
    """Print detailed help for one command. Returns False if unknown."""
    doc = next((item for item in COMMANDS if item.name == name), None)
    if doc is None:
        console.print(f"[yellow]没有名为 `{name}` 的命令；输入 `help` 查看全部命令。[/yellow]")
        return False

    console.print(f"[bold cyan]{doc.name}[/bold cyan] — {doc.summary}")
    console.print()
    console.print("  用法：")
    console.print(f"    {doc.usage}", markup=False, highlight=False)
    if doc.notes:
        console.print()
        console.print("  说明：")
        for note in doc.notes:
            console.print(f"    - {note}", markup=False, highlight=False)
    if doc.examples:
        console.print()
        console.print("  示例：")
        for example in doc.examples:
            console.print(f"    {example}", markup=False, highlight=False)
    console.print()
    return True


def configure_llm(console: Console) -> None:
    """Prompt for LLM settings and save them to the per-user config file."""
    settings = Settings.load()
    console.print("[bold]配置 LLM[/bold]（直接回车使用默认值）")
    base_url = Prompt.ask("  API 端点 base_url", default=settings.llm.base_url or DEFAULT_BASE_URL)
    model = Prompt.ask("  模型 model", default=settings.llm.model or DEFAULT_MODEL)
    api_key = Prompt.ask("  API key", password=True)
    if not api_key:
        console.print("[yellow]未输入 API key，已跳过。[/yellow]")
        return
    path = save_user_config(
        {
            "GAMELINK_LLM_BASE_URL": base_url,
            "GAMELINK_LLM_MODEL": model,
            "GAMELINK_LLM_API_KEY": api_key,
        }
    )
    console.print(f"[green]已保存到[/green] {path}")
