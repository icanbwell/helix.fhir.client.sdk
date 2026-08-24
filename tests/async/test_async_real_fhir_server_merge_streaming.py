"""End-to-end smoke tests that use_data_streaming(True) doesn't break real $merge calls
against a live FHIR server (real network round trip, real auth, real JSON parsing) -
a complement to the aioresponses-based tests, not a replacement for them.

These are NOT regression tests for the two bugs fixed in DCON-5232, and intentionally
so: verified locally (docker-compose's imranq2/node-fhir-server-mongo:6.7.9) that both
tests here pass identically whether or not either fix is applied, because:
  - This server's $merge response (still application/fhir+json) doesn't observably
    change based on the Accept header we send, so a missing "Accept: application/
    fhir+ndjson" isn't locally detectable from client-side behavior.
  - This server responds to malformed resources with a 200 and an embedded
    OperationOutcome-style issue rather than a 4xx/5xx, so the non-200 code path that
    RetryableAioHttpResponse.get_text_async() had a bug in is never exercised here.

The deterministic regression coverage for both bugs - proven to fail against the
pre-fix code and pass with the fix - lives in
helix_fhir_client_sdk/test/test_merge_accept_header.py (asserts the actual Accept
header the SDK sends) and
helix_fhir_client_sdk/test/test_merge_streaming_behavior.py (asserts diagnostics
survive a mocked non-200 streaming response). Keep these real-server tests as a
sanity check that streaming merges function end-to-end; don't rely on them to catch
a regression of either bug.
"""

import json
from logging import Logger
from os import environ

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers
from tests.logger_for_test import LoggerForTest


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_merge_streaming_success(use_data_streaming: bool) -> None:
    logger: Logger = LoggerForTest()
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(client_id=auth_client_id, client_secret=auth_client_secret)
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.use_data_streaming(use_data_streaming)

    resource = {
        "resourceType": "Patient",
        "id": "streaming-merge-test-1",
        "meta": {
            "source": "http://www.icanbwell.com",
            "security": [
                {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
            ],
        },
    }

    merge_response: FhirMergeResponse | None = await FhirMergeResponse.from_async_generator(
        fhir_client.merge_async(json_data_list=[json.dumps(resource)])
    )

    assert merge_response is not None
    logger.info(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert len(merge_response.responses) == 1, merge_response.responses
    assert merge_response.responses[0]["created"] is True, merge_response.responses


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_merge_streaming_preserves_issue_diagnostics(
    use_data_streaming: bool,
) -> None:
    logger: Logger = LoggerForTest()
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(client_id=auth_client_id, client_secret=auth_client_secret)
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.use_data_streaming(use_data_streaming)

    resource = {
        "resourceType": "Patient",
        "id": "streaming-merge-test-2",
        "meta": "bad",
    }

    merge_response: FhirMergeResponse | None = await FhirMergeResponse.from_async_generator(
        fhir_client.merge_async(json_data_list=[json.dumps(resource)])
    )

    assert merge_response is not None
    logger.info(merge_response.responses)
    assert merge_response.responses[0]["issue"] is not None, json.dumps(merge_response.responses)
