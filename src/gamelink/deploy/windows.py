"""Deploy a generated Godot server to a Windows cloud server (dev_plan_1.md §4.6).

Phase 0/1 skeleton: build a deploy plan and support ``--dry-run`` (default).
The real transfer path uses ``scp``/``ssh`` (OpenSSH for Windows) and is only
attempted when a host is configured and dry-run is disabled.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from gamelink.config import Settings
from gamelink.errors import DeployError
from gamelink.generate.godot import DEFAULT_PORT
from gamelink.options import DesignerOptions


@dataclass
class DeployPlan:
    server_dir: Path
    host: str | None
    user: str
    ssh_port: int
    key_path: str | None
    remote_dir: str
    game_port: int
    dry_run: bool

    @property
    def connect_address(self) -> str:
        host = self.host or "<host>"
        return f"{host}:{self.game_port}"

    def describe(self) -> str:
        steps = [
            f"upload  {self.server_dir} -> {self.user}@{self.host}:{self.remote_dir}",
            f"install Windows service (NSSM) listening on UDP {self.game_port}",
            f"allow inbound UDP {self.game_port} in Windows Firewall",
            f"connect at {self.connect_address}",
        ]
        return "\n".join(f"  - {step}" for step in steps)


@dataclass
class DeployResult:
    success: bool
    detail: str
    connect_address: str | None = None


def build_deploy_plan(
    server_dir: str | Path,
    settings: Settings,
    options: DesignerOptions,
    dry_run: bool = True,
) -> DeployPlan:
    deploy_settings = settings.deploy
    return DeployPlan(
        server_dir=Path(server_dir),
        host=deploy_settings.host,
        user=deploy_settings.user,
        ssh_port=deploy_settings.ssh_port,
        key_path=deploy_settings.key_path,
        remote_dir=deploy_settings.remote_dir,
        game_port=deploy_settings.game_port or DEFAULT_PORT,
        dry_run=dry_run,
    )


def deploy(plan: DeployPlan) -> DeployResult:
    if plan.dry_run:
        return DeployResult(
            success=True,
            detail="dry-run: no changes made\n" + plan.describe(),
            connect_address=plan.connect_address,
        )
    if not plan.host:
        raise DeployError("GAMELINK_DEPLOY_HOST is not set; cannot deploy")
    _upload(plan)
    _start_remote(plan)
    return DeployResult(
        success=True,
        detail=f"deployed to {plan.host}:{plan.remote_dir}",
        connect_address=plan.connect_address,
    )


def _ssh_base(plan: DeployPlan) -> list[str]:
    cmd = ["ssh", "-p", str(plan.ssh_port)]
    if plan.key_path:
        cmd += ["-i", plan.key_path]
    cmd.append(f"{plan.user}@{plan.host}")
    return cmd


def _upload(plan: DeployPlan) -> None:
    scp = ["scp", "-r", "-P", str(plan.ssh_port)]
    if plan.key_path:
        scp += ["-i", plan.key_path]
    scp += [str(plan.server_dir), f"{plan.user}@{plan.host}:{plan.remote_dir}"]
    try:
        subprocess.run(scp, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DeployError(f"upload failed: {exc}") from exc


def _start_remote(plan: DeployPlan) -> None:
    # TODO(Phase 1): run deploy/windows/install_service.ps1 (NSSM) to register the
    # headless server as a Windows service, then start it. For now, only open the
    # UDP port so a manually-started server is reachable.
    script = (
        f"New-NetFirewallRule -DisplayName 'GameLink UDP {plan.game_port}' "
        f"-Direction Inbound -Protocol UDP -LocalPort {plan.game_port} -Action Allow"
    )
    try:
        subprocess.run([*_ssh_base(plan), "-Command", script], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DeployError(f"remote start failed: {exc}") from exc
