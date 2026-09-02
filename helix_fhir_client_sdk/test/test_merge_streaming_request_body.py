"""Regression tests ensuring $merge requests serialize the outgoing payload as
newline-delimited JSON (one resource per line) when use_data_streaming() is
enabled and more than one resource is being sent, since the FHIR server's
streaming $merge only understands ndjson request bodies
(https://github.com/icanbwell/fhir-server/blob/main/readme/merge.md) - a JSON
array or a wrapped Bundle resource is not a valid streaming payload even
though it is valid for the non-streaming (buffered) $merge path.
"""

import json

import pytest
from aioresponses import aioresponses
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from yarl import URL

from helix_fhir_client_sdk.fhir_client import FhirClient

_PATIENT_1 = {"resourceType": "Patient", "id": "1"}
_PATIENT_2 = {"resourceType": "Patient", "id": "2"}


def _sent_body(m: aioresponses, method: str, url: str) -> str:
    calls = m.requests[(method, URL(url))]
    data = calls[-1].kwargs["data"]
    return data if isinstance(data, str) else data.decode("utf-8")


def _assert_is_ndjson(body: str, expected_resources: list[dict[str, str]]) -> None:
    lines = body.splitlines()
    assert len(lines) == len(expected_resources)
    assert [json.loads(line) for line in lines] == expected_resources


@pytest.mark.asyncio
async def test_merge_async_sends_ndjson_body_for_multiple_resources_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    json_data_list = [json.dumps(_PATIENT_1), json.dumps(_PATIENT_2)]

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        _ = [response async for response in fhir_client.merge_async(json_data_list=json_data_list)]

        _assert_is_ndjson(_sent_body(m, "POST", url), [_PATIENT_1, _PATIENT_2])


@pytest.mark.asyncio
async def test_merge_async_sends_json_array_body_for_multiple_resources_when_streaming_disabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient")
    json_data_list = [json.dumps(_PATIENT_1), json.dumps(_PATIENT_2)]

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        _ = [response async for response in fhir_client.merge_async(json_data_list=json_data_list)]

        assert json.loads(_sent_body(m, "POST", url)) == [_PATIENT_1, _PATIENT_2]


@pytest.mark.asyncio
async def test_merge_resources_async_sends_ndjson_body_for_multiple_resources_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        _ = [
            response
            async for response in fhir_client.merge_resources_async(
                id_="1",
                resources_to_merge=FhirResourceList([FhirResource(_PATIENT_1), FhirResource(_PATIENT_2)]),
                batch_size=None,
            )
        ]

        _assert_is_ndjson(_sent_body(m, "POST", url), [_PATIENT_1, _PATIENT_2])


@pytest.mark.asyncio
async def test_merge_resources_async_sends_json_array_body_when_streaming_disabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient")

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        _ = [
            response
            async for response in fhir_client.merge_resources_async(
                id_="1",
                resources_to_merge=FhirResourceList([FhirResource(_PATIENT_1), FhirResource(_PATIENT_2)]),
                batch_size=None,
            )
        ]

        assert json.loads(_sent_body(m, "POST", url)) == [_PATIENT_1, _PATIENT_2]


@pytest.mark.asyncio
async def test_merge_bundle_uncompressed_sends_ndjson_body_for_multiple_entries_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList(
            [
                FhirBundleEntry(resource=FhirResource(_PATIENT_1)),
                FhirBundleEntry(resource=FhirResource(_PATIENT_2)),
            ]
        ),
    )

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        await fhir_client.merge_bundle_uncompressed(id_="1", bundle=bundle)

        _assert_is_ndjson(_sent_body(m, "POST", url), [_PATIENT_1, _PATIENT_2])


@pytest.mark.asyncio
async def test_merge_bundle_uncompressed_sends_bundle_json_body_when_streaming_disabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient")
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList(
            [
                FhirBundleEntry(resource=FhirResource(_PATIENT_1)),
                FhirBundleEntry(resource=FhirResource(_PATIENT_2)),
            ]
        ),
    )

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        await fhir_client.merge_bundle_uncompressed(id_="1", bundle=bundle)

        sent = json.loads(_sent_body(m, "POST", url))
        assert sent["resourceType"] == "Bundle"


@pytest.mark.asyncio
async def test_merge_bundle_async_sends_ndjson_body_for_multiple_entries_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList(
            [
                FhirBundleEntry(resource=FhirResource(_PATIENT_1)),
                FhirBundleEntry(resource=FhirResource(_PATIENT_2)),
            ]
        ),
    )

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        _ = [response async for response in fhir_client.merge_bundle_async(id_="1", bundle=bundle)]

        _assert_is_ndjson(_sent_body(m, "POST", url), [_PATIENT_1, _PATIENT_2])
