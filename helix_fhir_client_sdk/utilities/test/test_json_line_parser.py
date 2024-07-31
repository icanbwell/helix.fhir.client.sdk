import json
from typing import Any, Dict, List, Optional

from helix_fhir_client_sdk.utilities.json_line_parser import JsonLineParser


def test_single_line_json() -> None:
    processor = JsonLineParser()
    result = processor.add_line('{"name": "John", "age": 30, "city": "New York"}')
    assert result == {"name": "John", "age": 30, "city": "New York"}


def test_multiline_json() -> None:
    processor = JsonLineParser()
    assert processor.add_line('{"name": "John", "age": 30, ') is None
    result = processor.add_line('"city": "New York"}')
    assert result == {"name": "John", "age": 30, "city": "New York"}


def test_invalid_json() -> None:
    processor = JsonLineParser()
    result = processor.add_line('{"name": "John", "age": 30, ')
    assert result is None
    result = processor.add_line('"city": "New York"')  # Missing closing brace
    assert result is None  # Should still return None due to incomplete JSON


def test_multiple_json_objects() -> None:
    processor = JsonLineParser()
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


def test_fhir_resources() -> None:
    fhir: Dict[str, Any] = {
        "resourceType": "Bundle",
        "total": 2,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
            {"resource": {"resourceType": "Patient", "id": "2"}},
        ],
    }

    fhir_json: str = ""
    for e in fhir["entry"]:
        fhir_json += json.dumps(e, indent=2) + "\n"
    print(fhir_json)
    fhir_json_lines: List[str] = fhir_json.split("\n")
    processor = JsonLineParser()
    results = []
    line_number = 0
    for line in fhir_json_lines:
        line_number += 1
        print(f"Line {line_number}: {line}")
        result: Optional[Dict[str, Any]] = processor.add_line(line)
        if result:
            print(f"Resource: {line_number}: {result}")
            results.append(result)
        else:
            print(f"{line_number}: None")
