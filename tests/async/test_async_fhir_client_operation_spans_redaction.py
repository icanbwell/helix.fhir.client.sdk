"""DCON-6540: the SDK operation spans (get, streaming get, merge, update, patch, delete) record the type of
an exception only. The exception messages contain the request URL, with its path ids and query values.

aioresponses mocks the FHIR server; SpanRecorder (tests/span_recorder.py) records the spans.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pytest
from aiohttp import ClientResponseError
from aioresponses import aioresponses
from opentelemetry.trace import StatusCode

from helix_fhir_client_sdk import (
    fhir_client as fhir_client_module,
)
from helix_fhir_client_sdk import (
    fhir_delete_mixin,
    fhir_merge_mixin,
    fhir_patch_mixin,
    fhir_update_mixin,
)
from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.utilities import retryable_aiohttp_client
from tests.span_recorder import SpanRecorder

BASE_URL = "http://fhir.example.test/4_0_0"
PATIENT_ID = "patient-test-001"
ACCESS_TOKEN = "synthetic-access-token-0001"
PATIENT_JSON = json.dumps({"resourceType": "Patient", "id": PATIENT_ID})
SEARCH_URL = f"{BASE_URL}/Observation?patient={PATIENT_ID}"
INSTANCE_URL = f"{BASE_URL}/Patient/{PATIENT_ID}"
VALUES_THAT_MUST_NOT_LEAK = (PATIENT_ID, ACCESS_TOKEN, "?")


def _search_client() -> FhirClient:
    return FhirClient().url(BASE_URL).resource("Observation").filter_by_resource("Patient").id_(PATIENT_ID)


def _instance_client() -> FhirClient:
    return FhirClient().url(BASE_URL).resource("Patient").id_(PATIENT_ID)


async def _get(client: FhirClient) -> None:
    await client.get_async()


async def _get_streaming(client: FhirClient) -> None:
    async for _ in client.get_streaming_async():
        pass


async def _merge(client: FhirClient) -> None:
    async for _ in client.merge_async(id_=PATIENT_ID, json_data_list=[PATIENT_JSON]):
        pass


async def _update(client: FhirClient) -> None:
    await client.update_async(json_data=PATIENT_JSON)


async def _patch(client: FhirClient) -> None:
    await client.send_patch_request_async(data=json.dumps([{"op": "replace", "path": "/active", "value": True}]))


async def _delete(client: FhirClient) -> None:
    await client.delete_async()


@dataclass(frozen=True)
class Operation:
    name: str
    span_name: str
    create_client: Callable[[], FhirClient]
    method: str
    url: str
    run: Callable[[FhirClient], Awaitable[None]]
    expected_error_type: type[Exception]


OPERATIONS = [
    Operation("get", "fhir.client_sdk.get", _search_client, "GET", SEARCH_URL, _get, FhirSenderException),
    Operation(
        "streaming-get",
        "fhir.client_sdk.streaming.get",
        _search_client,
        "GET",
        SEARCH_URL,
        _get_streaming,
        FhirSenderException,
    ),
    Operation(
        "merge",
        "fhir.client_sdk.merge",
        _instance_client,
        "POST",
        f"{INSTANCE_URL}/$merge",
        _merge,
        FhirSenderException,
    ),
    Operation("update", "fhir.client_sdk.update", _instance_client, "PUT", INSTANCE_URL, _update, ClientResponseError),
    Operation("patch", "fhir.client_sdk.patch", _instance_client, "PATCH", INSTANCE_URL, _patch, FhirSenderException),
    Operation(
        "delete", "fhir.client_sdk.delete", _instance_client, "DELETE", INSTANCE_URL, _delete, ClientResponseError
    ),
]


@pytest.mark.parametrize("operation", OPERATIONS, ids=[operation.name for operation in OPERATIONS])
async def test_operation_span_records_only_the_exception_type(
    operation: Operation, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    span_recorder = SpanRecorder()
    for module in (
        fhir_client_module,
        fhir_merge_mixin,
        fhir_update_mixin,
        fhir_patch_mixin,
        fhir_delete_mixin,
        retryable_aiohttp_client,
    ):
        monkeypatch.setattr(module, "TRACER", span_recorder)
    fhir_client = operation.create_client().set_access_token(ACCESS_TOKEN).retry_count(0)

    # Act
    with aioresponses() as fhir_server:
        fhir_server.add(operation.url, method=operation.method, status=500, repeat=True)
        with pytest.raises(operation.expected_error_type) as error_info:
            await operation.run(fhir_client)

    # Assert
    [operation_span] = span_recorder.spans_named(operation.span_name)
    assert operation_span.events == []
    assert operation_span.status.status_code == StatusCode.ERROR
    assert operation_span.status.description == type(error_info.value).__name__
    for span in span_recorder.spans:
        assert [value for value in VALUES_THAT_MUST_NOT_LEAK for text in span.recorded_texts() if value in text] == []
