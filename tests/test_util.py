import pytest

from gamelink.errors import AnalysisError
from gamelink.util import extract_json, slugify


def test_extract_json_from_fence():
    text = 'Here you go:\n```json\n{"a": 1}\n```\nDone.'
    assert extract_json(text) == {"a": 1}


def test_extract_json_from_prose():
    assert extract_json('prefix {"b": 2} suffix') == {"b": 2}


def test_extract_json_nested_object_in_fence():
    # A naive non-greedy fence regex would stop at the first inner "}" and break.
    text = '```json\n{"report": "hi", "protocol_spec": {"messages": [{"id": "x"}]}}\n```'
    parsed = extract_json(text)
    assert parsed["protocol_spec"]["messages"][0]["id"] == "x"


def test_extract_json_with_braces_inside_strings():
    text = '{"report": "use {curly} braces and } too", "protocol_spec": {"a": 1}}'
    parsed = extract_json(text)
    assert parsed["report"] == "use {curly} braces and } too"
    assert parsed["protocol_spec"] == {"a": 1}


def test_extract_json_ignores_prose_braces():
    text = 'prose {not json} then {"protocol_spec": {"a": 1}} trailing {oops}'
    assert extract_json(text) == {"protocol_spec": {"a": 1}}


def test_extract_json_repairs_trailing_comma():
    assert extract_json('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}


def test_extract_json_without_object_raises():
    with pytest.raises(AnalysisError):
        extract_json("no json here")


def test_extract_json_unparseable_raises():
    with pytest.raises(AnalysisError):
        extract_json('{"a": 1 "b": 2}')


def test_slugify():
    assert slugify("Snake Single!") == "snake-single"
    assert slugify("  ") == "project"
