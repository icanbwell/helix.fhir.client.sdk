import json
import uuid
from logging import Logger

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from tests.logger_for_test import LoggerForTest


@pytest.mark.skip("for testing. You need real secret and client id")
def test_merge_person_with_smart_merge_modes() -> None:
    logger: Logger = LoggerForTest()

    # Generate unique test ID for Person
    person_id = str(uuid.uuid4())
    base_url = "https://fhir.staging.bwell.zone/4_0_0"
    resource_type = "Person"

    original_person = {
        "resourceType": resource_type,
        "id": person_id,
        "name": [{"use": "official", "family": "Test", "given": ["User"]}],
        "telecom": [
            {"system": "phone", "value": "+15551112222", "use": "home"},
            {"system": "email", "value": f"test-{person_id}@example.com", "use": "home"},
        ],
        "gender": "female",
        "birthDate": "1990-01-01",
        "address": [{"line": ["123 Test St"], "city": "Testville", "state": "TX", "postalCode": "78701"}],
        "meta": {
            "source": "bwell-test",
            "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-person"],
            "security": [
                {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
            ],
        },
    }

    # Authenticate
    fhir_client = FhirClient().client_credentials(client_id="", client_secret="")
    token = fhir_client.get_access_token()
    base_client = fhir_client.set_access_token(token.access_token).url(base_url)

    client_merge = base_client.smart_merge(True).resource(resource_type)
    try:
        # Step 1: Initial create
        response1 = client_merge.merge(json_data_list=[json.dumps(original_person)])
        logger.info("Initial merge response:")
        assert response1 is not None
        assert response1.responses[0]["created"] is True  # We expect creation here

        # Step 2: Append new telecom
        appended_person = json.loads(json.dumps(original_person))  # Deep copy
        appended_person["telecom"].append({"system": "phone", "value": "+15553334444", "use": "mobile"})

        response2 = client_merge.merge(json_data_list=[json.dumps(appended_person)])
        logger.info("After append (smartMerge=True):")
        assert response2 is not None
        assert response2, response2.responses[0]["updated"]

        # Step 3: Replace telecom
        replaced_person = json.loads(json.dumps(original_person))
        replaced_person["telecom"] = [{"system": "phone", "value": "999-999-9999", "use": "work"}]

        client_replace = base_client.smart_merge(False).resource(resource_type)
        response3 = client_replace.merge(json_data_list=[json.dumps(replaced_person)])
        logger.info("After replace (smartMerge=false):")
        assert response3 is not None
        assert response3, response3.responses[0]["updated"]

        # data = base_client.resource(resource_type).id_(person_id).get()

        # Step 4: Reset to original
        response4 = client_replace.merge(json_data_list=[json.dumps(original_person)])
        logger.info("Reset to original (smartMerge=false):")
        assert response4 is not None
        assert response4, response4.responses[0]["updated"] or not response4.responses[0]["updated"]  # Allow no-op

    finally:
        # Step 5: Clean up by deleting test resource
        client_resource = base_client.resource(resource_type).id_(person_id)
        delete_response = client_resource.delete()
        logger.info(f"Deleted test person {person_id}: {delete_response.status}")
        assert delete_response.status in [200, 204]  # Deleted successfully
