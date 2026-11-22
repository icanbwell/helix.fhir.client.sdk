"""Regression tests ensuring non-ASCII values survive in $merge request bodies.

compressedfhir 5.x json() writes raw UTF-8 (4.x wrote \\uXXXX escapes), so a $merge body now carries
multi-byte characters on the wire. These tests check that every $merge body shape (single resource,
ndjson, JSON array, Bundle) is valid UTF-8 JSON that round-trips the values unchanged. Deploy this
SDK only after fhir-server's streaming $merge parser decodes multi-byte characters split across
request chunks (icanbwell/fhir-server#2775).
"""

import json
from typing import Any

import pytest
from aioresponses import aioresponses
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from yarl import URL

from helix_fhir_client_sdk.fhir_client import FhirClient

# synthetic, non-PHI value containing 2-byte and 3-byte UTF-8 characters
NON_ASCII_FAMILY = "Müller 山"
URL_MERGE = "http://example.com/Patient/1/$merge"


def _patients(count: int) -> list[dict[str, Any]]:
    return [
        {"resourceType": "Patient", "id": str(i), "name": [{"family": NON_ASCII_FAMILY}]} for i in range(1, count + 1)
    ]


def _sent_body(m: aioresponses) -> str:
    body = m.requests[("POST", URL(URL_MERGE))][-1].kwargs["data"]
    assert isinstance(body, str)
    return body


def _resources_in_body(body: str) -> list[dict[str, Any]]:
    """Parses a $merge body: ndjson lines, a JSON array, a Bundle, or a single resource."""
    documents: list[Any] = [json.loads(line) for line in body.split("\n")]
    resources: list[dict[str, Any]] = []
    for document in documents:
        if isinstance(document, list):
            resources.extend(document)
        elif document.get("resourceType") == "Bundle":
            resources.extend(entry["resource"] for entry in document["entry"])
        else:
            resources.append(document)
    return resources


def _assert_lossless(body: str, expected_count: int) -> None:
    resources = _resources_in_body(body)
    assert NON_ASCII_FAMILY in body
    assert len(resources) == expected_count
    assert all(r["name"][0]["family"] == NON_ASCII_FAMILY for r in resources)


@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize("count", [1, 3])
@pytest.mark.asyncio
async def test_merge_resources_async_sends_lossless_non_ascii_body(streaming: bool, count: int) -> None:
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(streaming)

    with aioresponses() as m:
        m.post(URL_MERGE, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [
            response
            async for response in fhir_client.merge_resources_async(
                id_="1",
                resources_to_merge=FhirResourceList([FhirResource(o) for o in _patients(count)]),
                batch_size=None,
            )
        ]

        _assert_lossless(_sent_body(m), count)


@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize("count", [1, 3])
@pytest.mark.asyncio
async def test_merge_bundle_async_sends_lossless_non_ascii_body(streaming: bool, count: int) -> None:
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(streaming)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource(o)) for o in _patients(count)]),
    )

    with aioresponses() as m:
        m.post(URL_MERGE, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [response async for response in fhir_client.merge_bundle_async(id_="1", bundle=bundle)]

        _assert_lossless(_sent_body(m), count)


@pytest.mark.parametrize("byte_identical_json", [False, True])
@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize("count", [1, 3])
@pytest.mark.asyncio
async def test_merge_resources_body_follows_byte_identical_json(
    byte_identical_json: bool, streaming: bool, count: int
) -> None:
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .resource("Patient")
        .use_data_streaming(streaming)
        .byte_identical_json(byte_identical_json)
    )

    with aioresponses() as m:
        m.post(URL_MERGE, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [
            response
            async for response in fhir_client.merge_resources_async(
                id_="1",
                resources_to_merge=FhirResourceList([FhirResource(o) for o in _patients(count)]),
                batch_size=None,
            )
        ]

        body = _sent_body(m)
        assert ("\\u00fc" in body) is byte_identical_json
        assert (NON_ASCII_FAMILY in body) is not byte_identical_json
        resources = _resources_in_body(body)
        assert len(resources) == count
        assert all(r["name"][0]["family"] == NON_ASCII_FAMILY for r in resources)


@pytest.mark.parametrize("byte_identical_json", [False, True])
@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.asyncio
async def test_merge_bundle_body_follows_byte_identical_json(byte_identical_json: bool, streaming: bool) -> None:
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .resource("Patient")
        .use_data_streaming(streaming)
        .byte_identical_json(byte_identical_json)
    )
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource(o)) for o in _patients(2)]),
    )

    with aioresponses() as m:
        m.post(URL_MERGE, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [response async for response in fhir_client.merge_bundle_async(id_="1", bundle=bundle)]

        body = _sent_body(m)
        assert ("\\u00fc" in body) is byte_identical_json
        assert len(_resources_in_body(body)) == 2
