"""Regression tests proving that $merge request body format and compression are
driven by self._content_type - the actual header value sent on the wire - rather
than the self._use_data_streaming flag. Found during adversarial review: since
.content_type()/.accept() are public setters that can be called independently of
use_data_streaming(), branching body/compress logic on the flag instead of the
header let the two drift apart (e.g. use_data_streaming(True).content_type(
"application/fhir+json") left the flag True but the header json), producing a
request whose Content-Type header and body format disagreed with each other.
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


def _sent_headers(m: aioresponses, method: str, url: str) -> dict[str, str]:
    calls = m.requests[(method, URL(url))]
    return dict(calls[-1].kwargs["headers"])


def _sent_body(m: aioresponses, method: str, url: str) -> str:
    calls = m.requests[(method, URL(url))]
    data = calls[-1].kwargs["data"]
    return data if isinstance(data, str) else data.decode("utf-8")


def _sent_compress(m: aioresponses, method: str, url: str) -> object:
    calls = m.requests[(method, URL(url))]
    return calls[-1].kwargs.get("compress", False)


@pytest.mark.asyncio
async def test_merge_async_body_matches_content_type_even_when_streaming_flag_says_otherwise() -> None:
    """use_data_streaming(True) followed by an explicit content_type() override must
    produce a body (and compress setting) consistent with the header actually sent,
    not with the now-stale use_data_streaming flag.
    """
    url = "http://example.com/Patient/1/$merge"
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .resource("Patient")
        .use_data_streaming(True)
        .content_type("application/fhir+json")
    )
    json_data_list = [json.dumps(_PATIENT_1), json.dumps(_PATIENT_2)]

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        _ = [response async for response in fhir_client.merge_async(json_data_list=json_data_list)]

        headers = _sent_headers(m, "POST", url)
        body = _sent_body(m, "POST", url)
        assert headers["Content-Type"] == "application/fhir+json"
        # body must be a JSON array, matching the json Content-Type - not ndjson lines
        assert json.loads(body) == [_PATIENT_1, _PATIENT_2]
        # compression must be allowed again since we're no longer sending ndjson
        assert _sent_compress(m, "POST", url) is True


@pytest.mark.asyncio
async def test_merge_async_sends_ndjson_body_from_content_type_alone_without_streaming_flag() -> None:
    """Setting content_type("application/fhir+ndjson") directly - without ever calling
    use_data_streaming() - must still produce an ndjson body and disable compression,
    since the header is the actual contract with the server.
    """
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient").content_type("application/fhir+ndjson")
    json_data_list = [json.dumps(_PATIENT_1), json.dumps(_PATIENT_2)]

    with aioresponses() as m:
        m.post(url, status=200, payload=[_PATIENT_1, _PATIENT_2])

        _ = [response async for response in fhir_client.merge_async(json_data_list=json_data_list)]

        body = _sent_body(m, "POST", url)
        lines = body.splitlines()
        assert [json.loads(line) for line in lines] == [_PATIENT_1, _PATIENT_2]
        assert (
            _sent_compress(
                m,
                "POST",
                url,
            )
            is False
        )


@pytest.mark.asyncio
async def test_merge_bundle_uncompressed_body_matches_content_type_override() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .resource("Patient")
        .use_data_streaming(True)
        .content_type("application/fhir+json")
    )
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
async def test_merge_resources_async_body_matches_content_type_override() -> None:
    url = "http://example.com/Patient/1/$merge"
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .resource("Patient")
        .use_data_streaming(True)
        .content_type("application/fhir+json")
    )

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
