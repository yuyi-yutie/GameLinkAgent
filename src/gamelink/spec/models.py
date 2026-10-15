"""Typed shapes for the two specs (documentation aid; validated by JSON Schema)."""

from __future__ import annotations

from typing import Literal, TypedDict

Direction = Literal["C2S", "S2C"]
RpcMode = Literal["authority", "any_peer"]
Transfer = Literal["reliable", "unreliable", "unreliable_ordered"]


class Param(TypedDict):
    name: str
    type: str


class Message(TypedDict, total=False):
    id: str
    direction: Direction
    rpc_mode: RpcMode
    transfer: Transfer
    params: list[Param]
    description: str


class ReplicatedField(TypedDict):
    name: str
    type: str


class StateNode(TypedDict, total=False):
    node: str
    authority: Literal["server", "client"]
    replicated: list[ReplicatedField]


class ProtocolSpec(TypedDict, total=False):
    game: str
    target_engine: str
    transport: str
    messages: list[Message]
    state: list[StateNode]


class Spawn(TypedDict):
    node: str
    spawner: str


class Refactor(TypedDict):
    name: str
    source: str
    action: str


class ArchitectureSpec(TypedDict, total=False):
    authority_model: Literal["server_authoritative", "client_authoritative", "hybrid"]
    tick_rate: int
    scene: dict
    spawns: list[Spawn]
    refactors: list[Refactor]
