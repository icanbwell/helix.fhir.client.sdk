import pytest

from helix_fhir_client_sdk.utilities.json_helpers import parse_json_or_ndjson


def test_parse_json_or_ndjson_single_object() -> None:
    assert parse_json_or_ndjson('{"resourceType": "Patient", "id": "1"}') == {
        "resourceType": "Patient",
        "id": "1",
    }


def test_parse_json_or_ndjson_array() -> None:
    assert parse_json_or_ndjson('[{"id": "1"}, {"id": "2"}]') == [{"id": "1"}, {"id": "2"}]


def test_parse_json_or_ndjson_newline_delimited() -> None:
    text = '{"id": "1"}\n{"id": "2"}\n{"id": "3"}'
    assert parse_json_or_ndjson(text) == [{"id": "1"}, {"id": "2"}, {"id": "3"}]


def test_parse_json_or_ndjson_newline_delimited_with_blank_lines() -> None:
    text = '{"id": "1"}\n\n{"id": "2"}\n'
    assert parse_json_or_ndjson(text) == [{"id": "1"}, {"id": "2"}]


def test_parse_json_or_ndjson_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_json_or_ndjson("not json\nstill not json")
