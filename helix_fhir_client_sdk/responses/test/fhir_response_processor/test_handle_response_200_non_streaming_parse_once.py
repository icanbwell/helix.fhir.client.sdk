import json
from logging import Logger
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)
from helix_fhir_client_sdk.responses.get.fhir_get_response_factory import (
    FhirGetResponseFactory,
)
from helix_fhir_client_sdk.utilities.retryable_aiohttp_response import (
    RetryableAioHttpResponse,
)

# Synthetic resources only
PATIENT: dict[str, Any] = {"resourceType": "Patient", "id": "p1", "active": True}
OBSERVATION: dict[str, Any] = {
    "resourceType": "Observation",
    "id": "o1",
    "status": "final",
    "valueQuantity": {"value": 1.5, "unit": "mg"},
}
SEARCH_PAGE: dict[str, Any] = {
    "resourceType": "Bundle",
    "id": "b1",
    "type": "searchset",
    "total": 7,
    "link": [
        {"relation": "self", "url": "https://example.com/fhir/Observation?_count=2"},
        {"relation": "next", "url": "https://example.com/fhir/Observation?_count=2&page=2"},
    ],
    "entry": [
        {"fullUrl": "https://example.com/fhir/Patient/p1", "resource": PATIENT},
        {"resource": OBSERVATION, "response": {"status": "200", "etag": 'W/"2"'}},
    ],
}
ONE_ENTRY_PAGE: dict[str, Any] = {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": PATIENT}]}
EMPTY_PAGE: dict[str, Any] = {"resourceType": "Bundle", "type": "searchset", "total": 0}


def _response(text: str) -> MagicMock:
    response = MagicMock(RetryableAioHttpResponse)
    response.ok = True
    response.status = 200
    response.results_by_url = []
    response.get_text_async = AsyncMock(return_value=text)
    return response


def _kwargs(*, expand_fhir_bundle: bool, storage_mode: CompressedDictStorageMode) -> dict[str, Any]:
    return {
        "full_url": "https://example.com/fhir/Observation",
        "request_id": "request-1",
        "access_token": None,
        "response_headers": ['ETag: W/"9"'],
        "resources_json": "",
        "next_url": None,
        "total_count": 0,
        "logger": MagicMock(Logger),
        "expand_fhir_bundle": expand_fhir_bundle,
        "separate_bundle_resources": False,
        "extra_context_to_return": None,
        "resource": "Observation",
        "id_": None,
        "url": "https://example.com/fhir",
        "storage_mode": storage_mode,
        "create_operation_outcome_for_error": False,
    }


async def _text_path_reference(text: str, kwargs: dict[str, Any]) -> FhirGetResponse:
    """What the handler produced before: serialize the expanded resources to text, then let the factory parse it"""
    response_json = json.loads(text)
    next_url = kwargs["next_url"]
    if isinstance(response_json, dict) and response_json.get("resourceType") == "Bundle":
        for link in response_json.get("link", []):
            if link.get("relation") == "next":
                next_url = link.get("url")
                break
    resources_json, total_count = await FhirResponseProcessor.expand_or_separate_bundle_async(
        access_token=kwargs["access_token"],
        expand_fhir_bundle=kwargs["expand_fhir_bundle"],
        extra_context_to_return=kwargs["extra_context_to_return"],
        resource_or_bundle=response_json,
        separate_bundle_resources=False,
        total_count=kwargs["total_count"],
        url=kwargs["url"],
    )
    return FhirGetResponseFactory.create(
        request_id=kwargs["request_id"],
        url=kwargs["full_url"],
        response_text=resources_json,
        error=None,
        access_token=kwargs["access_token"],
        total_count=total_count,
        status=200,
        next_url=next_url,
        extra_context_to_return=kwargs["extra_context_to_return"],
        resource_type=kwargs["resource"],
        id_=kwargs["id_"],
        response_headers=kwargs["response_headers"],
        results_by_url=[],
        storage_mode=kwargs["storage_mode"],
        create_operation_outcome_for_error=False,
    )


def _observable_output(response: FhirGetResponse) -> dict[str, Any]:
    return {
        "class": type(response).__name__,
        "to_dict": response.to_dict(),
        "response_text": response.get_response_text(),
        "bundle_entries": [entry.dict() for entry in response.get_bundle_entries()],
        "next_url": response.next_url,
        "total_count": response.total_count,
    }


@pytest.mark.parametrize("storage_mode", [CompressedDictStorageMode.raw(), CompressedDictStorageMode.compressed()])
@pytest.mark.parametrize("expand_fhir_bundle", [True, False])
@pytest.mark.parametrize(
    "body",
    [SEARCH_PAGE, ONE_ENTRY_PAGE, EMPTY_PAGE, PATIENT, [PATIENT, OBSERVATION]],
    ids=["search_page", "one_entry_page", "empty_page", "single_resource", "json_list"],
)
async def test_non_streaming_output_matches_text_path(
    body: dict[str, Any] | list[dict[str, Any]],
    expand_fhir_bundle: bool,
    storage_mode: CompressedDictStorageMode,
) -> None:
    # Arrange
    text = json.dumps(body)
    kwargs = _kwargs(expand_fhir_bundle=expand_fhir_bundle, storage_mode=storage_mode)
    expected = await _text_path_reference(text, kwargs)

    # Act
    results = [
        r async for r in FhirResponseProcessor._handle_response_200_non_streaming(response=_response(text), **kwargs)
    ]

    # Assert
    assert len(results) == 1
    assert _observable_output(results[0]) == _observable_output(expected)


@pytest.mark.parametrize("expand_fhir_bundle", [True, False])
async def test_non_streaming_parses_page_once_and_does_not_reserialize(
    expand_fhir_bundle: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    text = json.dumps(SEARCH_PAGE)
    kwargs = _kwargs(expand_fhir_bundle=expand_fhir_bundle, storage_mode=CompressedDictStorageMode.raw())
    real_loads, real_dumps = json.loads, json.dumps
    loads_calls: list[Any] = []
    dumps_calls: list[Any] = []

    def counting_loads(s: Any, *args: Any, **kw: Any) -> Any:
        loads_calls.append(s)
        return real_loads(s, *args, **kw)

    def counting_dumps(o: Any, *args: Any, **kw: Any) -> Any:
        dumps_calls.append(o)
        return real_dumps(o, *args, **kw)

    monkeypatch.setattr(json, "loads", counting_loads)
    monkeypatch.setattr(json, "dumps", counting_dumps)

    # Act
    results = [
        r async for r in FhirResponseProcessor._handle_response_200_non_streaming(response=_response(text), **kwargs)
    ]

    # Assert
    assert results[0].get_resource_count() == 2
    assert len(loads_calls) == 1
    assert dumps_calls == []
