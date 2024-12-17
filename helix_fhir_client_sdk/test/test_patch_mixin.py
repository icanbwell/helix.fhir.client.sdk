import json

import pytest
from typing import Dict, Any

from aioresponses import aioresponses

from helix_fhir_client_sdk.fhir_client import FhirClient


@pytest.mark.asyncio
async def test_patch_async_success() -> None:
    """Test successful patch_async call."""
    url = "http://example.com/Observation/1"
    fhir_client = FhirClient().url(url).resource("Observation")

    obs_updated_payload: Dict[str, Any] = {
        "resourceType": "Observation",
        "id": "1",
        "code": {
            "coding": [
                {
                    "id": "adbq8e47brct83v6",
                    "extension": [
                        {
                            "id": "preferred",
                            "url": "https://fhir.icanbwell.com/4_0_0/StructureDefinition/intelligence",
                            "valueCode": "preferred",
                        }
                    ],
                    "system": "http://hl7.org/fhir",
                    "code": "HL7",
                    "display": "HL7",
                }
            ]
        },
    }
    print(json.dumps(obs_updated_payload))

    with aioresponses() as m:
        m.post(
            "http://validation-server.com/Observation/$validate", status=200, payload={}
        )
        m.post(url, status=200, payload=obs_updated_payload)
        fhir_client._url = "http://example.com"
        fhir_client._resource = "Observation"
        fhir_client._id = "1"
        fhir_client._validation_server_url = "http://validation-server.com"

        response = await fhir_client.send_patch_request_async(
            data=json.dumps(obs_updated_payload)
        )
        print(response)

        # assert response.status == 200
        # assert response.responses[0]["resourceType"] == "Observation"
