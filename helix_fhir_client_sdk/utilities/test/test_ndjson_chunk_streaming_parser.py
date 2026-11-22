import json
from logging import Logger
from typing import Any

import pytest

from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
    NdJsonInvalidLineError,
)
from tests.logger_for_test import LoggerForTest

logger: Logger = LoggerForTest()


def test_ndjson_chunk_streaming_parser_single_line() -> None:
    data_chunks = ['{"name": "John", "age": 30}']
    parser = NdJsonChunkStreamingParser()

    all_objects: list[dict[str, Any]] = []
    all_objects_by_chunk: list[list[dict[str, Any]]] = []

    chunk_number = 0
    for chunk in data_chunks:
        chunk_number += 1
        complete_json_objects = parser.add_chunk(chunk, logger=None)
        logger.info(f"{chunk_number}: ", complete_json_objects)
        all_objects.extend(complete_json_objects)
        all_objects_by_chunk.append(complete_json_objects)

    logger.info("All JSON objects:", all_objects)
    assert len(all_objects) == 1
    assert all_objects[0] == {"name": "John", "age": 30}


def test_ndjson_chunk_streaming_parser() -> None:
    data_chunks = [
        '{"name": "John", "age": 30}\n{"name": "Jane", "a',
        'ge": 25}\n{"name": "Doe", "age": 40}\n{"name":',
        ' "Smith", "age',
        '": 35}\n',
    ]

    parser = NdJsonChunkStreamingParser()

    all_objects: list[dict[str, Any]] = []
    all_objects_by_chunk: list[list[dict[str, Any]]] = []

    chunk_number = 0
    for chunk in data_chunks:
        chunk_number += 1
        complete_json_objects = parser.add_chunk(chunk, logger=None)
        logger.info(f"{chunk_number}: ", complete_json_objects)
        all_objects.extend(complete_json_objects)
        all_objects_by_chunk.append(complete_json_objects)

    logger.info("All JSON objects:", all_objects)
    assert len(all_objects) == 4
    assert all_objects[0] == {"name": "John", "age": 30}
    assert all_objects[1] == {"name": "Jane", "age": 25}
    assert all_objects[2] == {"name": "Doe", "age": 40}
    assert all_objects[3] == {"name": "Smith", "age": 35}

    assert len(all_objects_by_chunk) == 4
    assert len(all_objects_by_chunk[0]) == 1
    assert all_objects_by_chunk[0][0] == {"name": "John", "age": 30}
    assert len(all_objects_by_chunk[1]) == 2
    assert all_objects_by_chunk[1][0] == {"name": "Jane", "age": 25}
    assert all_objects_by_chunk[1][1] == {"name": "Doe", "age": 40}
    assert len(all_objects_by_chunk[2]) == 0
    assert len(all_objects_by_chunk[3]) == 1
    assert all_objects_by_chunk[3][0] == {"name": "Smith", "age": 35}


def test_add_chunk_single_complete_object() -> None:
    parser = NdJsonChunkStreamingParser()
    chunk = '{"name": "John", "age": 30}\n'
    result = parser.add_chunk(chunk, logger=None)
    expected_result = [{"name": "John", "age": 30}]
    assert result == expected_result


def test_add_chunk_multiple_complete_objects() -> None:
    parser = NdJsonChunkStreamingParser()
    chunk = '{"name": "John", "age": 30}\n{"name": "Jane", "age": 25}\n'
    result = parser.add_chunk(chunk, logger=None)
    expected_result = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]
    assert result == expected_result


def test_add_chunk_incomplete_object() -> None:
    parser = NdJsonChunkStreamingParser()
    chunk = '{"name": "John", "age": 30'
    result: list[dict[str, Any]] = parser.add_chunk(chunk, logger=None)
    expected_result: list[dict[str, Any]] = []
    assert result == expected_result
    assert parser.buffer == chunk


def test_add_chunk_complete_and_incomplete_objects() -> None:
    parser = NdJsonChunkStreamingParser()
    chunk = '{"name": "John", "age": 30}\n{"name": "Jane", "age": 25'
    result = parser.add_chunk(chunk, logger=None)
    expected_result: list[dict[str, Any]] = [{"name": "John", "age": 30}]
    assert result == expected_result


def test_add_chunk_incomplete_then_complete_object() -> None:
    parser = NdJsonChunkStreamingParser()
    chunk1 = '{"name": "John", "age": 30'
    chunk2 = '}\n{"name": "Jane", "age": 25}\n'
    parser.add_chunk(chunk1, logger=None)
    result = parser.add_chunk(chunk2, logger=None)
    expected_result: list[dict[str, Any]] = [
        {"name": "John", "age": 30},
        {"name": "Jane", "age": 25},
    ]
    assert result == expected_result


def test_add_chunk_empty_chunk() -> None:
    parser = NdJsonChunkStreamingParser()
    chunk = ""
    result = parser.add_chunk(chunk, logger=None)
    expected_result: list[dict[str, Any]] = []
    assert result == expected_result


def test_add_chunk_mixed_complete_and_incomplete_objects() -> None:
    parser = NdJsonChunkStreamingParser()
    chunk1 = '{"name": "John", "age": 30}\n{"name": "Jane", "age": 25'
    chunk2 = '}\n{"name": "Doe", "age": 40}\n'
    result = parser.add_chunk(chunk1, logger=None)
    assert result == [{"name": "John", "age": 30}]
    result = parser.add_chunk(chunk2, logger=None)
    expected_result: list[dict[str, Any]] = [
        {"name": "Jane", "age": 25},
        {"name": "Doe", "age": 40},
    ]
    assert result == expected_result


def test_add_chunk_no_newline_at_the_end() -> None:
    parser = NdJsonChunkStreamingParser()
    chunk = '{"name": "John", "age": 30}\n{"name": "Jane", "age": 25}'
    result = parser.add_chunk(chunk, logger=None)
    expected_result: list[dict[str, Any]] = [
        {"name": "John", "age": 30},
        {"name": "Jane", "age": 25},
    ]
    assert result == expected_result


# Synthetic lines only (no PHI).
_VALID_FIRST = '{"id": "first"}'
_VALID_LAST = '{"id": "last"}'


@pytest.mark.parametrize("bad_line", ["{bad", '{"id": "truncated"', "[1, 2,]"])
def test_invalid_line_in_the_middle_of_a_stream_raises(bad_line: str) -> None:
    parser = NdJsonChunkStreamingParser()
    chunk = f"{_VALID_FIRST}\n{bad_line}\n{_VALID_LAST}\n"

    with pytest.raises(json.JSONDecodeError):
        parser.add_chunk(chunk, logger=None)


# orjson rejects these; the standard library accepts them, so a line holding one is still delivered
@pytest.mark.parametrize("line", ['{"id": NaN}', '{"id": "\\ud800"}', '{"id": 1e400}'])
@pytest.mark.parametrize("byte_identical_json", [False, True])
def test_line_only_the_standard_library_accepts_is_delivered_in_both_modes(
    line: str, byte_identical_json: bool
) -> None:
    parser = NdJsonChunkStreamingParser(byte_identical_json=byte_identical_json)

    result = parser.add_chunk(f"{_VALID_FIRST}\n{line}\n{_VALID_LAST}\n", logger=None)

    assert len(result) == 3
    assert result[0] == {"id": "first"}
    assert result[2] == {"id": "last"}


def test_partial_final_line_is_held_until_the_next_chunk() -> None:
    parser = NdJsonChunkStreamingParser()

    first = parser.add_chunk(f'{_VALID_FIRST}\n{{"id": "la', logger=None)
    second = parser.add_chunk('st"}\n', logger=None)

    assert first == [{"id": "first"}]
    assert second == [{"id": "last"}]


def test_invalid_line_carries_the_objects_parsed_before_it() -> None:
    parser = NdJsonChunkStreamingParser()

    with pytest.raises(NdJsonInvalidLineError) as exc_info:
        parser.add_chunk(f"{_VALID_FIRST}\n{{bad\n{_VALID_LAST}\n", logger=None)

    assert exc_info.value.parsed == [{"id": "first"}]
    assert isinstance(exc_info.value, json.JSONDecodeError)
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize("byte_identical_json", [False, True])
def test_chunk_boundary_inside_a_record_does_not_mark_the_span_as_an_error(
    monkeypatch: pytest.MonkeyPatch, byte_identical_json: bool
) -> None:
    attributes: dict[str, Any] = {}

    class _Span:
        def is_recording(self) -> bool:
            return True

        def set_attribute(self, key: str, value: Any) -> None:
            attributes[key] = value

    monkeypatch.setattr("helix_fhir_client_sdk.utilities.fast_json.trace.get_current_span", lambda: _Span())
    parser = NdJsonChunkStreamingParser(byte_identical_json=byte_identical_json)

    parser.add_chunk(f'{_VALID_FIRST}\n{{"id": "la', logger=None)
    parser.add_chunk('st"}\n', logger=None)

    assert "json.error" not in attributes
