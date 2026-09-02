"""Regression tests ensuring $merge requests never ask aiohttp to gzip-compress the
outgoing body when use_data_streaming() is enabled. Compression forces chunked
transfer encoding (the compressed length isn't known up front), and the FHIR
server's streaming ndjson $merge parser returns a malformed response (a 400 whose
raw headers include both Content-Length and Transfer-Encoding, which aiohttp
refuses to parse) when it receives a chunked, gzip-encoded request body - verified
against a live local FHIR server (imranq2/node-fhir-server-mongo:6.7.9). Since
FhirClient defaults compress to True, every streaming $merge call would fail
end-to-end without this.
"""

import json
from typing import cast

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


def _sent_kwargs(m: aioresponses, method: str, url: str) -> dict[str, object]:
    calls = m.requests[(method, URL(url))]
    return cast(dict[str, object], calls[-1].kwargs)


@pytest.mark.asyncio
async def test_merge_async_disables_compress_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)

    with aioresponses() as m:
        m.post(url, status=200, payload=_PATIENT_1)

        _ = [response async for response in fhir_client.merge_async(json_data_list=[json.dumps(_PATIENT_1)])]

        assert _sent_kwargs(m, "POST", url).get("compress", False) is False


@pytest.mark.asyncio
async def test_merge_async_keeps_default_compress_when_streaming_disabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient")

    with aioresponses() as m:
        m.post(url, status=200, payload=_PATIENT_1)

        _ = [response async for response in fhir_client.merge_async(json_data_list=[json.dumps(_PATIENT_1)])]

        assert _sent_kwargs(m, "POST", url).get("compress") is True


@pytest.mark.asyncio
async def test_merge_resources_async_disables_compress_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)

    with aioresponses() as m:
        m.post(url, status=200, payload=_PATIENT_1)

        _ = [
            response
            async for response in fhir_client.merge_resources_async(
                id_="1",
                resources_to_merge=FhirResourceList([FhirResource(_PATIENT_1)]),
                batch_size=None,
            )
        ]

        assert _sent_kwargs(m, "POST", url).get("compress", False) is False


@pytest.mark.asyncio
async def test_merge_bundle_uncompressed_disables_compress_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource(_PATIENT_1))]),
    )

    with aioresponses() as m:
        m.post(url, status=200, payload=_PATIENT_1)

        await fhir_client.merge_bundle_uncompressed(id_="1", bundle=bundle)

        assert _sent_kwargs(m, "POST", url).get("compress", False) is False


@pytest.mark.asyncio
async def test_merge_bundle_async_disables_compress_when_streaming_enabled() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").use_data_streaming(True)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource(_PATIENT_1))]),
    )

    with aioresponses() as m:
        m.post(url, status=200, payload=_PATIENT_1)

        _ = [response async for response in fhir_client.merge_bundle_async(id_="1", bundle=bundle)]

        assert _sent_kwargs(m, "POST", url).get("compress", False) is False
