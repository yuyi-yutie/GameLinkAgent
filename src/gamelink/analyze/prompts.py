"""Prompt construction for network-semantics analysis."""

from __future__ import annotations

import json
from typing import Any

from gamelink.options import DesignerOptions

SYSTEM_PROMPT = """\
You are GameLink Agent's network-semantics analyzer for Godot 4 games.
Your job: read a single-player Godot project and produce a structured plan for
converting it into a server-authoritative multiplayer game using Godot's native
high-level multiplayer (ENetMultiplayerPeer, @rpc, MultiplayerSynchronizer,
MultiplayerSpawner).

Classify every relevant piece of logic:
- server-authoritative state (movement stepping, collision, scoring, win/lose)
- client presentation (rendering, input capture, animation, UI)
- network messages (client intents, discrete server events)

Rules:
- Clients send INTENTS; the server owns authoritative STATE.
- Prefer state synchronization for continuous state and RPC events for discrete
  moments (food eaten, game over).
- Only reference nodes, autoloads and scripts that actually appear in the project.

Language:
- Write the "report" field in Simplified Chinese (简体中文), as Markdown.
- Write human-readable "description" fields in Simplified Chinese too.
- Keep identifiers, file paths, node/class names and API names (e.g. @rpc,
  MultiplayerSynchronizer, res://scripts/main.gd) in their original form.

Return ONE JSON object with exactly these keys:
  "report":         the analysis written in Chinese (markdown string)
  "protocol_spec":  object conforming to the protocol schema below
  "architecture_spec": object conforming to the architecture schema below
Do not wrap the JSON in prose outside the object.
"""


def build_analysis_prompt(
    project_summary: str,
    options: DesignerOptions,
    protocol_schema: dict[str, Any],
    architecture_schema: dict[str, Any],
) -> tuple[str, str]:
    user = f"""\
## Designer options
{json.dumps(options.to_dict(), ensure_ascii=False, indent=2)}

## protocol.spec JSON Schema
{json.dumps(protocol_schema, ensure_ascii=False, indent=2)}

## server-architecture.spec JSON Schema
{json.dumps(architecture_schema, ensure_ascii=False, indent=2)}

## Godot project
{project_summary}
"""
    return SYSTEM_PROMPT, user
