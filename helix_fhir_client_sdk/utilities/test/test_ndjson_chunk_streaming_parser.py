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
        complete_json_objects = parser.add_chunk(chunk, logger=None)
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
        complete_json_objects = parser.add_chunk(chunk, logger=None)
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


# def test_ndjson_chunk_streaming_parser_line_with_newline() -> None:
#     print("")
#     data_chunks = [
#         '{"resourceType":"Patient","id":"3456789012345670303","meta":{"profile":["http://hl7.org/fhir/us/carin/StructureDefinition/carin-bb-coverage"]}\n,"identifier":[{"type":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/v2-0203","code":"SN"}]},"system":"https://sources.aetna.com/coverage/identifier/membershipid/59","value":"435679010300+AE303+2021-01-01"}],"status":"active","type":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/v3-ActCode","code":"PPO","display":"preferred provider organization policy"}]},"policyHolder":{"reference":"Patient/1234567890123456703","type":"Patient"},"subscriber":{"reference":"Patient/1234567890123456703","type":"Patient"},"subscriberId":"435679010300","beneficiary":{"reference":"Patient/1234567890123456703","type":"Patient"},"relationship":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/subscriber-relationship","code":"self"}]},"period":{"start":"2021-01-01","end":"2021-12-31"},"payor":[{"reference":"Organization/6667778889990000014","type":"Organization","display":"Aetna"}],"class":[{"type":{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/coverage-class","code":"plan","display":"Plan"}]},"value":"AE303","name":"Aetna Plan"}],"network":"Medicare - MA/NY/NJ - Full Reciprocity","costToBeneficiary":[{"type":{"text":"Annual Physical Exams NMC - In Network"},"valueQuantity":{"value":50,"unit":"$","system":"http://aetna.com/Medicare/CostToBeneficiary/ValueQuantity/code"}}]}',
#         "",
#     ]
#
#     parser = NdJsonChunkStreamingParser()
#
#     all_objects: List[Dict[str, Any]] = []
#     all_objects_by_chunk: List[List[Dict[str, Any]]] = []
#
#     chunk_number = 0
#     for chunk in data_chunks:
#         chunk_number += 1
#         complete_json_objects = parser.add_chunk(chunk, logger=None)
#         print(f"{chunk_number}: ", complete_json_objects)
#         all_objects.extend(complete_json_objects)
#         all_objects_by_chunk.append(complete_json_objects)
#
#     print("All JSON objects:", all_objects)
#     assert len(all_objects) == 1
