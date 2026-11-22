"""Regression tests ensuring $merge request bodies stay ASCII-escaped.

compressedfhir 5.x writes raw UTF-8 from json() by default, and fhir-server's streaming $merge
parser corrupts a multi-byte character that is split across two request chunks
(icanbwell/fhir-server#2775). The SDK therefore asks for json(byte_identical=True) when it builds
a $merge body, so no multi-byte character ever reaches the wire.
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


def _assert_ascii_and_lossless(body: str, expected_count: int) -> None:
    resources = _resources_in_body(body)
    assert body.isascii()
    assert len(resources) == expected_count
    assert all(r["name"][0]["family"] == NON_ASCII_FAMILY for r in resources)


@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize("count", [1, 3])
@pytest.mark.asyncio
async def test_merge_resources_async_sends_ascii_escaped_body(streaming: bool, count: int) -> None:
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

        _assert_ascii_and_lossless(_sent_body(m), count)


@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize("count", [1, 3])
@pytest.mark.asyncio
async def test_merge_bundle_async_sends_ascii_escaped_body(streaming: bool, count: int) -> None:
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(streaming)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource(o)) for o in _patients(count)]),
    )

    with aioresponses() as m:
        m.post(URL_MERGE, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [response async for response in fhir_client.merge_bundle_async(id_="1", bundle=bundle)]

        _assert_ascii_and_lossless(_sent_body(m), count)
