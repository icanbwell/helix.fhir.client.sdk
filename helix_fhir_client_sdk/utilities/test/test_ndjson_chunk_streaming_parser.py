from typing import Any, Dict, List

from helix_fhir_client_sdk.utilities.ndjson_chunk_streaming_parser import (
    NdJsonChunkStreamingParser,
)


def test_ndjson_chunk_streaming_parser_single_line() -> None:
    data_chunks = ['{"name": "John", "age": 30}']
    parser = NdJsonChunkStreamingParser()

    all_objects: List[Dict[str, Any]] = []
    all_objects_by_chunk: List[List[Dict[str, Any]]] = []

    chunk_number = 0
    for chunk in data_chunks:
        chunk_number += 1
        complete_json_objects = parser.add_chunk(chunk)
        print(f"{chunk_number}: ", complete_json_objects)
        all_objects.extend(complete_json_objects)
        all_objects_by_chunk.append(complete_json_objects)

    print("All JSON objects:", all_objects)
    assert len(all_objects) == 1
    assert all_objects[0] == {"name": "John", "age": 30}


def test_ndjson_chunk_streaming_parser() -> None:
    print("")
    data_chunks = [
        '{"name": "John", "age": 30}\n{"name": "Jane", "a',
        'ge": 25}\n{"name": "Doe", "age": 40}\n{"name":',
        ' "Smith", "age',
        '": 35}\n',
    ]

    parser = NdJsonChunkStreamingParser()

    all_objects: List[Dict[str, Any]] = []
    all_objects_by_chunk: List[List[Dict[str, Any]]] = []

    chunk_number = 0
    for chunk in data_chunks:
        chunk_number += 1
        complete_json_objects = parser.add_chunk(chunk)
        print(f"{chunk_number}: ", complete_json_objects)
        all_objects.extend(complete_json_objects)
        all_objects_by_chunk.append(complete_json_objects)

    print("All JSON objects:", all_objects)
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
