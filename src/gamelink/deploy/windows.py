"""Package a generated Godot project into a deployable Windows server bundle.

"One-click deploy" produces, under ``<server_dir>/dist/``:

* ``<slug>-server.exe``  — the exported headless dedicated server
* ``使用说明.md``         — a step-by-step deployment guide
* ``scripts/*.ps1``      — firewall + Windows service (NSSM) helpers

Pushing to a remote host is intentionally out of scope: the bundle is
self-contained so the operator can copy it to the server and follow the guide.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from gamelink.config import Settings
from gamelink.errors import DeployError
from gamelink.generate.godot import DEFAULT_PORT, SERVER_PRESET
from gamelink.options import DesignerOptions
from gamelink.resources import render_template
from gamelink.util import slugify

GUIDE_NAME = "使用说明.md"

_HELPERS = {
    "scripts/install_service.ps1": ("deploy", "windows", "install_service.ps1.tmpl"),
    "scripts/open_firewall.ps1": ("deploy", "windows", "open_firewall.ps1.tmpl"),
}


@dataclass
class DeployPlan:
    server_dir: Path
    dist_dir: Path
    game: str
    slug: str
    exe_name: str
    service_name: str
    preset: str
    port: int
    max_players: int

    @property
    def exe_path(self) -> Path:
        return self.dist_dir / self.exe_name

    def describe(self) -> str:
        steps = (
            f"导出 headless 服务端 -> {self.exe_path}",
            f"写出部署说明 -> {self.dist_dir / GUIDE_NAME}",
            "随包附带 scripts/open_firewall.ps1 与 scripts/install_service.ps1",
            f"部署后客户端连接 <服务器公网IP>:{self.port}",
        )
        return "\n".join(f"  - {step}" for step in steps)


@dataclass
class DeployResult:
    dist_dir: Path
    exe_path: Path | None = None
    guide_path: Path | None = None
    files: list[Path] = field(default_factory=list)


def load_manifest(server_dir: str | Path) -> dict:
    """Read the ``gamelink/server.json`` manifest written by ``generate``."""
    path = Path(server_dir) / "gamelink" / "server.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def build_deploy_plan(
    server_dir: str | Path,
    settings: Settings,
    options: DesignerOptions,
    out_dir: str | Path | None = None,
) -> DeployPlan:
    server = Path(server_dir)
    manifest = load_manifest(server)
    game = str(manifest.get("game") or server.name)
    slug = str(manifest.get("slug") or slugify(game))
    return DeployPlan(
        server_dir=server,
        dist_dir=Path(out_dir) if out_dir is not None else server / "dist",
        game=game,
        slug=slug,
        exe_name=str(manifest.get("exe_name") or f"{slug}-server.exe"),
        service_name=str(manifest.get("service_name") or f"{slug}-server"),
        preset=str(manifest.get("preset") or SERVER_PRESET),
        port=int(manifest.get("port") or settings.deploy.game_port or DEFAULT_PORT),
        max_players=int(manifest.get("max_players") or options.max_players),
    )


def _context(plan: DeployPlan) -> dict[str, object]:
    return {
        "game": plan.game,
        "slug": plan.slug,
        "exe_name": plan.exe_name,
        "service_name": plan.service_name,
        "preset": plan.preset,
        "port": plan.port,
        "max_players": plan.max_players,
    }


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DeployError(f"执行命令失败：{exc}") from exc


def export_server(plan: DeployPlan, godot_bin: str | None, timeout: int = 900) -> Path:
    """Export the headless dedicated server and return the executable path."""
    if not godot_bin or not Path(godot_bin).exists():
        raise DeployError("未配置 Godot 引擎（GAMELINK_GODOT_BIN），无法导出服务端")

    project_dir = plan.server_dir.resolve()
    if not (project_dir / "project.godot").is_file():
        raise DeployError(f"不是 Godot 工程目录：{project_dir}")

    dist_dir = plan.dist_dir.resolve()
    dist_dir.mkdir(parents=True, exist_ok=True)
    exe_path = dist_dir / plan.exe_name

    # Godot needs absolute paths here, and a prior import pass on a fresh checkout.
    _run([godot_bin, "--headless", "--path", str(project_dir), "--import"], timeout)
    proc = _run(
        [
            godot_bin,
            "--headless",
            "--path",
            str(project_dir),
            "--export-release",
            plan.preset,
            str(exe_path),
        ],
        timeout,
    )
    if not exe_path.is_file():
        detail = (proc.stderr or proc.stdout or "").strip()[-800:]
        raise DeployError(f"导出失败（preset={plan.preset}）：\n{detail}")
    return exe_path


def package(plan: DeployPlan, godot_bin: str | None, timeout: int = 900) -> DeployResult:
    """Export the server, then write the deployment guide and helper scripts."""
    exe = export_server(plan, godot_bin, timeout)
    context = _context(plan)
    result = DeployResult(dist_dir=plan.dist_dir, exe_path=exe, files=[exe])

    guide = plan.dist_dir / GUIDE_NAME
    guide.write_text(
        render_template(context, "deploy", "windows", "DEPLOY.md.tmpl"), encoding="utf-8"
    )
    result.guide_path = guide
    result.files.append(guide)

    for rel_path, parts in _HELPERS.items():
        target = plan.dist_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_template(context, *parts), encoding="utf-8")
        result.files.append(target)

    return result
