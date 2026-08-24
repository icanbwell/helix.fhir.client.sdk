"""Regression tests ensuring $merge requests advertise the client's configured
Accept header (in particular application/fhir+ndjson when use_data_streaming()
is enabled) on every merge code path, since the FHIR server only streams back
an ndjson response for $merge when it is asked to via the Accept header.
"""

import pytest
from aioresponses import aioresponses
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from yarl import URL

from helix_fhir_client_sdk.fhir_client import FhirClient


def _sent_headers(m: aioresponses, method: str, url: str) -> dict[str, str]:
    calls = m.requests[(method, URL(url))]
    return dict(calls[-1].kwargs["headers"])


@pytest.mark.asyncio
async def test_merge_async_sends_ndjson_accept_header_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    json_data_list = ['{"resourceType": "Patient", "id": "1"}']

    with aioresponses() as m:
        m.post(url, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [response async for response in fhir_client.merge_async(json_data_list=json_data_list)]

        assert _sent_headers(m, "POST", url)["Accept"] == "application/fhir+ndjson"


@pytest.mark.asyncio
async def test_merge_async_sends_default_accept_header_when_streaming_disabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient")
    json_data_list = ['{"resourceType": "Patient", "id": "1"}']

    with aioresponses() as m:
        m.post(url, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [response async for response in fhir_client.merge_async(json_data_list=json_data_list)]

        assert _sent_headers(m, "POST", url)["Accept"] == "application/fhir+json"


@pytest.mark.asyncio
async def test_merge_resources_async_sends_ndjson_accept_header_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    json_data_list = [{"resourceType": "Patient", "id": "1"}]

    with aioresponses() as m:
        m.post(url, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [
            response
            async for response in fhir_client.merge_resources_async(
                id_="1",
                resources_to_merge=FhirResourceList([FhirResource(o) for o in json_data_list]),
                batch_size=None,
            )
        ]

        assert _sent_headers(m, "POST", url)["Accept"] == "application/fhir+ndjson"


@pytest.mark.asyncio
async def test_merge_bundle_uncompressed_sends_ndjson_accept_header_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource({"resourceType": "Patient", "id": "1"}))]),
    )

    with aioresponses() as m:
        m.post(url, status=200, payload={"resourceType": "Patient", "id": "1"})

        await fhir_client.merge_bundle_uncompressed(id_="1", bundle=bundle)

        assert _sent_headers(m, "POST", url)["Accept"] == "application/fhir+ndjson"


@pytest.mark.asyncio
async def test_merge_bundle_async_sends_ndjson_accept_header_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource({"resourceType": "Patient", "id": "1"}))]),
    )

    with aioresponses() as m:
        m.post(url, status=200, payload={"resourceType": "Patient", "id": "1"})

        _ = [response async for response in fhir_client.merge_bundle_async(id_="1", bundle=bundle)]

        assert _sent_headers(m, "POST", url)["Accept"] == "application/fhir+ndjson"
