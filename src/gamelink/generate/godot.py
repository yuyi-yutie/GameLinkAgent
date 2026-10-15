"""Generate a Godot server project from a spec (dev_plan_1.md §4.4).

Phase 1 generator for the "single world + entities" class of small games
(Snake is the reference implementation). It copies the input project (keeping
its assets and scenes), then writes the networking layer from templates,
parameterised by the spec:

* RPC names come from ``protocol.spec.yaml`` (message ids);
* tick rate / autoloads come from ``server-architecture.spec.yaml``;
* transport / player count come from the designer options.

This is the "template-driven generation layer": new game classes add templates,
they do not change the generator.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gamelink.errors import GenerateError
from gamelink.ingest import GodotProject
from gamelink.options import DesignerOptions
from gamelink.resources import template_path
from gamelink.spec.io import dump_yaml

DEFAULT_PORT = 7000

TRANSPORT_CLASSES = {
    "enet": "ENetMultiplayerPeer",
    "websocket": "WebSocketMultiplayerPeer",
    "webrtc": "WebRTCMultiplayerPeer",
}

# Files the generator owns, relative to the project root -> template path.
_GENERATED = {
    "scripts/network_manager.gd": "godot/NetworkManager.gd.tmpl",
    "scripts/main.gd": "godot/main.gd.tmpl",
    "scripts/snake.gd": "godot/snake.gd.tmpl",
}

_AUTOLOAD_NAME = "NetworkManager"
_AUTOLOAD_PATH = "res://scripts/network_manager.gd"

_IGNORE = shutil.ignore_patterns(".godot", ".import", "out", "__pycache__", "*.exe", "*.pck")


@dataclass
class GenerateResult:
    out_dir: Path
    files: list[Path] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)


def _render(text: str, context: dict[str, Any]) -> str:
    for key, value in context.items():
        text = text.replace("{{ " + key + " }}", str(value))
        text = text.replace("{{" + key + "}}", str(value))
    return text


def _render_template(rel_path: str, context: dict[str, Any]) -> str:
    source = template_path(*rel_path.split("/"))
    if not source.exists():
        raise GenerateError(f"missing template: {rel_path}")
    return _render(source.read_text(encoding="utf-8"), context)


def _rpc_names(protocol: dict[str, Any]) -> tuple[str, str]:
    """Pick the client->server and server->client RPC names from the spec."""
    rpc_input, rpc_food = "submit_direction", "sync_food"
    for message in protocol.get("messages", []):
        if message.get("id") and message.get("direction") == "C2S":
            rpc_input = message["id"]
            break
    for message in protocol.get("messages", []):
        if message.get("id") and message.get("direction") == "S2C":
            rpc_food = message["id"]
            break
    return rpc_input, rpc_food


def _add_autoload(text: str, name: str, res_path: str) -> str:
    """Insert ``Name="*res://..."`` into the ``[autoload]`` section of project.godot."""
    entry = f'{name}="*{res_path}"'
    if re.search(rf"^{re.escape(name)}=", text, re.MULTILINE):
        return text
    if "[autoload]" in text:
        head, tail = text.split("[autoload]", 1)
        head += "[autoload]"
        match = re.search(r"\n\[", tail)
        if match:
            tail = tail[: match.start()] + f"\n{entry}\n" + tail[match.start():]
        else:
            tail = tail.rstrip("\n") + f"\n{entry}\n"
        return head + tail
    return text.rstrip("\n") + f"\n\n[autoload]\n\n{entry}\n"


def generate_server(
    project: GodotProject,
    options: DesignerOptions,
    protocol: dict[str, Any],
    architecture: dict[str, Any],
    out_dir: str | Path,
) -> GenerateResult:
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(project.root, out, ignore=_IGNORE)

    rpc_input, rpc_food = _rpc_names(protocol)
    context: dict[str, Any] = {
        "game": protocol.get("game", project.name),
        "transport_class": TRANSPORT_CLASSES.get(options.transport, "ENetMultiplayerPeer"),
        "port": DEFAULT_PORT,
        "tick_rate": architecture.get("tick_rate", options.tick_rate),
        "max_players": options.max_players,
        "authority_model": architecture.get("authority_model", options.authority_model),
        "rpc_input": rpc_input,
        "rpc_food": rpc_food,
    }

    result = GenerateResult(out_dir=out)
    for rel_out, template_rel in _GENERATED.items():
        target = out / rel_out
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_render_template(template_rel, context), encoding="utf-8")
        result.files.append(target)

    config = out / "project.godot"
    if not config.exists():
        raise GenerateError(f"input project has no project.godot: {config}")
    config.write_text(
        _add_autoload(config.read_text(encoding="utf-8"), _AUTOLOAD_NAME, _AUTOLOAD_PATH),
        encoding="utf-8",
    )
    result.files.append(config)

    result.files.append(dump_yaml(protocol, out / "gamelink/protocol.spec.yaml"))
    result.files.append(dump_yaml(architecture, out / "gamelink/server-architecture.spec.yaml"))

    for refactor in architecture.get("refactors", []):
        result.todos.append(
            f"[{refactor.get('action', 'review')}] {refactor.get('source', '?')} "
            f"-> {refactor.get('name', 'unnamed')}"
        )
    return result
