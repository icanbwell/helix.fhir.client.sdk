import copy
import json
from os import environ
from typing import Any, List, Dict

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers
from tests.test_logger import TestLogger


@pytest.mark.parametrize("use_data_streaming", [True, False])
async def test_async_real_fhir_server_get_patients_large(
    use_data_streaming: bool,
) -> None:
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")

    environ["LOGLEVEL"] = "DEBUG"

    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    logger = TestLogger()

    fhir_client = FhirClient()
    fhir_client.logger(logger=logger)
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    print("Deleting 1000 patients")
    for i in range(1000):
        patient_id = f"example-{i}"
        await fhir_client.id_(patient_id).delete_async()
    print("Deleted 1000 patients")

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)

    # now create 1000 patients
    patient = {
        "resourceType": "Patient",
        "id": "example",
        "meta": {
            "source": "http://www.icanbwell.com",
            "security": [
                {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
            ],
        },
        "text": {
            "status": "generated",
            "div": '<div xmlns="http://www.w3.org/1999/xhtml">John Doe</div>',
        },
        "identifier": [
            {
                "use": "usual",
                "type": {
                    "coding": [{"system": "http://hl7.org/fhir/v2/0203", "code": "MR"}]
                },
                "system": "http://example.com",
                "value": "12345",
            }
        ],
        "active": True,
        "name": [{"use": "official", "family": "Doe", "given": ["John"]}],
        "gender": "male",
        "birthDate": "1990-01-01",
        "address": [
            {
                "use": "home",
                "line": ["123 Main St"],
                "city": "Anytown",
                "state": "CA",
                "postalCode": "12345",
                "country": "USA",
            }
        ],
    }

    # add 1000 patients
    print("Adding 1000 patients")
    patients: List[Dict[str, Any]] = []
    for i in range(1000):
        patient_new = copy.deepcopy(patient)
        patient_new["id"] = f"example-{i}"
        patient_new["identifier"][0]["value"] = f"12345-{i}"  # type: ignore[index]
        patient_new["name"][0]["family"] = f"Doe-{i}"  # type: ignore[index]
        patient_new["name"][0]["given"][0] = f"John-{i}"  # type: ignore[index]
        patient_new["address"][0]["line"][0] = f"123 Main St-{i}"  # type: ignore[index]
        patient_new["address"][0]["city"] = f"Anytown-{i}"  # type: ignore[index]
        patient_new["address"][0]["state"] = f"CA-{i}"  # type: ignore[index]
        patient_new["address"][0]["postalCode"] = f"12345-{i}"  # type: ignore[index]
        patient_new["address"][0]["country"] = f"USA-{i}"  # type: ignore[index]
        patients.append(patient_new)
    print("Added 1000 patients")

    resource = {
        "resourceType": "Bundle",
        "id": "12355",
        "meta": {
            "source": "http://www.icanbwell.com",
            "security": [
                {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
            ],
        },
        "entry": [{"resource": p} for p in patients],
    }
    merge_response: FhirMergeResponse = await FhirMergeResponse.from_async_generator(
        fhir_client.merge_async(json_data_list=[json.dumps(resource)])
    )
    print(merge_response.responses)
    assert merge_response.status == 200, merge_response.responses
    assert len(merge_response.responses) == 1000, merge_response.responses
    assert merge_response.responses[0]["created"] is True, merge_response.responses

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(fhir_server_url).resource("Patient")
    fhir_client = fhir_client.client_credentials(
        client_id=auth_client_id, client_secret=auth_client_secret
    )
    fhir_client = fhir_client.auth_wellknown_url(auth_well_known_url)
    fhir_client = fhir_client.expand_fhir_bundle(False)
    fhir_client = fhir_client.limit(1000)
    fhir_client = fhir_client.use_data_streaming(use_data_streaming)
    response: FhirGetResponse = await fhir_client.get_async()
    response_text = response.responses

    if use_data_streaming:
        resources: List[Dict[str, Any]] = response.get_resources()
        assert len(resources) == 1
        assert resources[0]["id"] == resource["id"]
        assert resources[0]["resourceType"] == resource["resourceType"]
        assert response.chunk_number == 1
        assert response.response_headers is not None
        assert "Transfer-Encoding:chunked" in response.response_headers
    else:
        bundle = json.loads(response_text)
        assert "entry" in bundle, bundle
        responses_: List[Any] = [r["resource"] for r in bundle["entry"]]
        assert len(responses_) == 1000
        assert responses_[0]["id"].startswith("example-")
        assert responses_[0]["resourceType"] == "Patient"
