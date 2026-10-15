"""Designer-facing generation options (see dev_plan_1.md §3.3).

These are the choices the designer makes after the project is analyzed; they
directly drive the generated spec and server code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Literal

AuthorityModel = Literal["server_authoritative", "client_authoritative", "hybrid"]
SyncMechanism = Literal["state", "event", "state+event", "lockstep"]
Transport = Literal["enet", "websocket", "webrtc"]
RoomMode = Literal["single", "room_list", "matchmaking"]
Persistence = Literal["none", "sqlite", "redis"]
DeployTarget = Literal["local_docker", "windows_server"]


@dataclass
class DesignerOptions:
    authority_model: AuthorityModel = "server_authoritative"
    sync_mechanism: SyncMechanism = "state+event"
    transport: Transport = "enet"
    room_mode: RoomMode = "single"
    max_players: int = 4
    tick_rate: int = 15
    persistence: Persistence = "none"
    deploy_target: DeployTarget = "windows_server"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DesignerOptions:
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in allowed})


# Human-readable choices for the interactive CLI prompt.
OPTION_CHOICES: dict[str, list[str]] = {
    "authority_model": ["server_authoritative", "client_authoritative", "hybrid"],
    "sync_mechanism": ["state", "event", "state+event", "lockstep"],
    "transport": ["enet", "websocket", "webrtc"],
    "room_mode": ["single", "room_list", "matchmaking"],
    "persistence": ["none", "sqlite", "redis"],
    "deploy_target": ["local_docker", "windows_server"],
}
