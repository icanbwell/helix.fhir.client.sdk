import json
from typing import Any

import pytest
from aioresponses import aioresponses
from compressedfhir.fhir.fhir_resource import FhirResource
from yarl import URL

from helix_fhir_client_sdk.fhir_client import FhirClient

# Synthetic, non-PHI resource with a non-ASCII value.
PATIENT: dict[str, Any] = {"resourceType": "Patient", "id": "1", "name": [{"family": "Müller"}]}
URL_UPDATE = "http://example.com/Patient/1"


@pytest.mark.parametrize("byte_identical_json", [False, True])
@pytest.mark.asyncio
async def test_update_single_resource_body_follows_byte_identical_json(byte_identical_json: bool) -> None:
    fhir_client = (
        FhirClient().url("http://example.com").resource("Patient").id_("1").byte_identical_json(byte_identical_json)
    )

    with aioresponses() as m:
        m.put(URL_UPDATE, status=200, payload=PATIENT)

        await fhir_client.update_single_resource_async(resource=FhirResource(PATIENT))

        body = m.requests[("PUT", URL(URL_UPDATE))][-1].kwargs["data"]
        assert ("\\u00fc" in body) is byte_identical_json
        assert json.loads(body) == PATIENT
