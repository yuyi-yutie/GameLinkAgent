from pathlib import Path

import pytest

from gamelink.errors import SpecValidationError
from gamelink.spec import read_specs, validate_protocol, write_specs

REPO = Path(__file__).resolve().parents[1]
SPECS = REPO / "examples" / "snake-specs"


def test_example_specs_are_valid():
    protocol, architecture = read_specs(SPECS)
    assert protocol["game"] == "snake"
    assert protocol["messages"][0]["id"] == "submit_direction"
    assert architecture["authority_model"] == "server_authoritative"


def test_roundtrip(tmp_path):
    protocol, architecture = read_specs(SPECS)
    write_specs(protocol, architecture, tmp_path)
    protocol2, architecture2 = read_specs(tmp_path)
    assert protocol2 == protocol
    assert architecture2 == architecture


def test_invalid_spec_rejected():
    with pytest.raises(SpecValidationError):
        validate_protocol({"game": "x", "messages": [{"id": "a", "direction": "BAD"}]})


def test_missing_required_field_rejected():
    with pytest.raises(SpecValidationError):
        validate_protocol({"messages": []})
