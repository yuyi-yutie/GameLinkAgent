import pytest

from gamelink.errors import AnalysisError
from gamelink.util import extract_json, slugify


def test_extract_json_from_fence():
    text = 'Here you go:\n```json\n{"a": 1}\n```\nDone.'
    assert extract_json(text) == {"a": 1}


def test_extract_json_from_prose():
    assert extract_json('prefix {"b": 2} suffix') == {"b": 2}


def test_extract_json_without_object_raises():
    with pytest.raises(AnalysisError):
        extract_json("no json here")


def test_slugify():
    assert slugify("Snake Single!") == "snake-single"
    assert slugify("  ") == "project"
