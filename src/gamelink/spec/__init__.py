"""Spec assets: the two YAML specs, their schemas, and helpers."""

from gamelink.spec.io import (
    ARCHITECTURE_SCHEMA,
    PROTOCOL_SCHEMA,
    dump_yaml,
    load_schema,
    load_yaml,
    read_specs,
    validate_architecture,
    validate_instance,
    validate_protocol,
    write_specs,
)
from gamelink.spec.verify import Issue, verify_consistency

__all__ = [
    "ARCHITECTURE_SCHEMA",
    "PROTOCOL_SCHEMA",
    "Issue",
    "dump_yaml",
    "load_schema",
    "load_yaml",
    "read_specs",
    "validate_architecture",
    "validate_instance",
    "validate_protocol",
    "verify_consistency",
    "write_specs",
]
