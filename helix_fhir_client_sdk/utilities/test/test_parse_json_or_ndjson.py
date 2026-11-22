import json

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


@pytest.mark.parametrize(
    "separator",
    ["\u2028", "\u2029", "\u0085"],
    ids=["line-separator", "paragraph-separator", "next-line"],
)
def test_parse_json_or_ndjson_keeps_unicode_line_separator_inside_record(separator: str) -> None:
    records = [
        {"id": "1", "text": f"first{separator}half"},
        {"id": "2", "text": f"second{separator}half"},
    ]
    text = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)

    assert parse_json_or_ndjson(text) == records


def test_parse_json_or_ndjson_crlf_line_endings() -> None:
    text = '{"id": "1"}\r\n{"id": "2"}\r\n'

    assert parse_json_or_ndjson(text) == [{"id": "1"}, {"id": "2"}]
