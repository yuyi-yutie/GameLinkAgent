"""Read, write and validate the two YAML specs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from gamelink.errors import SpecValidationError
from gamelink.resources import schema_path

PROTOCOL_SCHEMA = "protocol.spec.schema.json"
ARCHITECTURE_SCHEMA = "server-architecture.spec.schema.json"

PROTOCOL_FILENAME = "protocol.spec.yaml"
ARCHITECTURE_FILENAME = "server-architecture.spec.yaml"


def load_schema(name: str) -> dict[str, Any]:
    return json.loads(schema_path(name).read_text(encoding="utf-8"))


def validate_instance(instance: Any, schema: dict[str, Any], label: str = "spec") -> None:
    try:
        Draft202012Validator(schema).validate(instance)
    except ValidationError as exc:
        location = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise SpecValidationError(f"{label} invalid at '{location}': {exc.message}") from exc


def validate_protocol(spec: dict[str, Any]) -> None:
    validate_instance(spec, load_schema(PROTOCOL_SCHEMA), "protocol.spec")


def validate_architecture(spec: dict[str, Any]) -> None:
    validate_instance(spec, load_schema(ARCHITECTURE_SCHEMA), "server-architecture.spec")


def load_yaml(path: str | Path) -> Any:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def dump_yaml(obj: Any, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(obj, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def write_specs(
    protocol: dict[str, Any],
    architecture: dict[str, Any],
    out_dir: str | Path,
) -> tuple[Path, Path]:
    """Validate and write both specs into ``out_dir``."""
    validate_protocol(protocol)
    validate_architecture(architecture)
    out = Path(out_dir)
    return (
        dump_yaml(protocol, out / PROTOCOL_FILENAME),
        dump_yaml(architecture, out / ARCHITECTURE_FILENAME),
    )


def read_specs(specs_dir: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    directory = Path(specs_dir)
    protocol = load_yaml(directory / PROTOCOL_FILENAME)
    architecture = load_yaml(directory / ARCHITECTURE_FILENAME)
    validate_protocol(protocol)
    validate_architecture(architecture)
    return protocol, architecture
