"""End-to-end smoke tests for the other three $merge call sites - merge_resources_async,
merge_bundle_uncompressed, and merge_bundle_async - against a live FHIR server, mirroring
test_async_real_fhir_server_merge_streaming.py's coverage of merge_async. Each is
parametrized over use_data_streaming and sent more than one resource, since a single
resource never exercises the ndjson-vs-JSON-array request body difference.

Same caveat as the sibling file: this local docker-compose FHIR server
(imranq2/node-fhir-server-mongo:6.7.9) doesn't observably change behavior based on the
request Content-Type/Accept headers we send, so these are round-trip smoke tests, not
regression tests for the request-body format. The deterministic regression coverage for
the request body itself (proven to fail before the fix, pass after) lives in
helix_fhir_client_sdk/test/test_merge_streaming_request_body.py.
"""

from logging import Logger
from os import environ

import pytest
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.merge.fhir_merge_resource_response import (
    FhirMergeResourceResponse,
)
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers
from tests.logger_for_test import LoggerForTest


def _make_patients(prefix: str, count: int) -> list[dict[str, object]]:
    return [
        {
            "resourceType": "Patient",
            "id": f"{prefix}-{i}",
            "meta": {
                "source": "http://www.icanbwell.com",
                "security": [
                    {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                    {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
                ],
            },
        }
        for i in range(1, count + 1)
    ]


def _configured_client(use_data_streaming: bool) -> FhirClient:
    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(client_id=auth_client_id, client_secret=auth_client_secret)
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    return fhir_client.use_data_streaming(use_data_streaming)


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_merge_resources_async_multiple_resources(use_data_streaming: bool) -> None:
    logger: Logger = LoggerForTest()
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    fhir_client = _configured_client(use_data_streaming)
    resources = _make_patients("streaming-merge-resources-test", 3)

    responses: list[FhirMergeResourceResponse] = [
        response
        async for response in fhir_client.merge_resources_async(
            id_="1",
            resources_to_merge=FhirResourceList([FhirResource(r) for r in resources]),
            batch_size=None,
        )
    ]

    assert len(responses) == 1
    merge_response = responses[0]
    logger.info(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert len(merge_response.responses) == len(resources), merge_response.responses
    assert all(entry.created is True for entry in merge_response.responses), merge_response.responses


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_merge_bundle_uncompressed_multiple_entries(use_data_streaming: bool) -> None:
    logger: Logger = LoggerForTest()
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    fhir_client = _configured_client(use_data_streaming)
    resources = _make_patients("streaming-merge-bundle-uncompressed-test", 3)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource(r)) for r in resources]),
    )

    merge_response: FhirMergeResourceResponse = await fhir_client.merge_bundle_uncompressed(id_="1", bundle=bundle)

    logger.info(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert len(merge_response.responses) == len(resources), merge_response.responses
    assert all(entry.created is True for entry in merge_response.responses), merge_response.responses


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_merge_bundle_async_multiple_entries(use_data_streaming: bool) -> None:
    logger: Logger = LoggerForTest()
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    fhir_client = _configured_client(use_data_streaming)
    resources = _make_patients("streaming-merge-bundle-async-test", 3)
    bundle = FhirBundle(
        type_="batch",
        entry=FhirBundleEntryList([FhirBundleEntry(resource=FhirResource(r)) for r in resources]),
    )

    responses: list[FhirMergeResourceResponse] = [
        response async for response in fhir_client.merge_bundle_async(id_="1", bundle=bundle)
    ]

    assert len(responses) == 1
    merge_response = responses[0]
    logger.info(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert len(merge_response.responses) == len(resources), merge_response.responses
    assert all(entry.created is True for entry in merge_response.responses), merge_response.responses
