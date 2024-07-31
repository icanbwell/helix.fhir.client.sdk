from typing import Dict, Any, Optional, List

from helix_fhir_client_sdk.utilities.json_bundle_streaming_parser import (
    JsonBundleStreamingParser,
)


def test_single_line_json() -> None:
    processor = JsonBundleStreamingParser()
    result = processor.add_line('{"name": "John", "age": 30, "city": "New York"}')
    assert result == {"name": "John", "age": 30, "city": "New York"}


def test_multiline_json() -> None:
    processor = JsonBundleStreamingParser()
    assert processor.add_line('{"name": "John", "age": 30, ') is None
    result = processor.add_line('"city": "New York"}')
    assert result == {"name": "John", "age": 30, "city": "New York"}


def test_invalid_json() -> None:
    processor = JsonBundleStreamingParser()
    result = processor.add_line('{"name": "John", "age": 30, ')
    assert result is None
    result = processor.add_line('"city": "New York"')  # Missing closing brace
    assert result is None  # Should still return None due to incomplete JSON


def test_multiple_json_objects() -> None:
    processor = JsonBundleStreamingParser()
    assert processor.add_line('{"name": "John", "age": 30, "city": "New York"}') == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert processor.add_line('{"name": "Anna", "age": 22, "city": "London"}') == {
        "name": "Anna",
        "age": 22,
        "city": "London",
    }


def test_bundle_json() -> None:
    print("")
    processor = JsonBundleStreamingParser()
    lines = [
        "{",
        '"resourceType": "Bundle",',
        '"entry": [',
        "{",
        '"resource": {',
        '"resourceType": "Patient"',
        "}",
        "},",
        "{",
        '"resource": {',
        '"resourceType": "Condition"',
        "}",
        "}",
        "]",
        "}",
    ]
    results: List[Optional[Dict[str, Any]]] = []
    line_number = 0
    for line in lines:
        line_number += 1
        result: Optional[Dict[str, Any]] = processor.add_line(line)
        if result:
            print(f"{line_number}: {result}")
            results.append(result)
        else:
            print(f"{line_number}: {result}")

    assert results == [
        {"resource": {"resourceType": "Patient"}},
        {"resource": {"resourceType": "Condition"}},
    ]
