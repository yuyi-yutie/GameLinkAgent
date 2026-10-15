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

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gamelink.errors import GenerateError
from gamelink.ingest import GodotProject
from gamelink.options import DesignerOptions
from gamelink.resources import render_template
from gamelink.spec.io import dump_yaml
from gamelink.util import slugify

DEFAULT_PORT = 7000
SERVER_PRESET = "Dedicated Server"

TRANSPORT_CLASSES = {
    "enet": "ENetMultiplayerPeer",
    "websocket": "WebSocketMultiplayerPeer",
    "webrtc": "WebRTCMultiplayerPeer",
}

# Files the generator owns, relative to the project root -> template path.
_GENERATED = {
    "export_presets.cfg": "godot/export_presets.cfg.tmpl",
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


def _render_template(rel_path: str, context: dict[str, Any]) -> str:
    try:
        return render_template(context, *rel_path.split("/"))
    except FileNotFoundError as exc:
        raise GenerateError(str(exc)) from exc


_POSITION_HINTS = {"pos", "position", "food"}


def _has_position_param(message: dict[str, Any]) -> bool:
    for param in message.get("params") or []:
        if param.get("name") in _POSITION_HINTS and "Vector2i" in str(param.get("type", "")):
            return True
    return False


def _rpc_names(protocol: dict[str, Any]) -> tuple[str, str]:
    """Pick the client->server intent RPC and the server->client food RPC names."""
    messages = protocol.get("messages", [])
    rpc_input = next(
        (m["id"] for m in messages if m.get("id") and m.get("direction") == "C2S"),
        "submit_direction",
    )
    rpc_food = next(
        (
            m["id"]
            for m in messages
            if m.get("id") and m.get("direction") == "S2C" and _has_position_param(m)
        ),
        None,
    )
    if rpc_food is None:
        rpc_food = next(
            (m["id"] for m in messages if m.get("id") and m.get("direction") == "S2C"),
            "sync_food",
        )
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
    game = str(protocol.get("game", project.name))
    slug = slugify(game)
    context: dict[str, Any] = {
        "game": game,
        "slug": slug,
        "exe_name": f"{slug}-server.exe",
        "service_name": f"{slug}-server",
        "preset": SERVER_PRESET,
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

    manifest = {
        "game": game,
        "slug": slug,
        "exe_name": context["exe_name"],
        "service_name": context["service_name"],
        "preset": SERVER_PRESET,
        "port": DEFAULT_PORT,
        "max_players": options.max_players,
        "transport": options.transport,
    }
    manifest_path = out / "gamelink" / "server.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    result.files.append(manifest_path)

    for refactor in architecture.get("refactors", []):
        result.todos.append(
            f"[{refactor.get('action', 'review')}] {refactor.get('source', '?')} "
            f"-> {refactor.get('name', 'unnamed')}"
        )
    return result
