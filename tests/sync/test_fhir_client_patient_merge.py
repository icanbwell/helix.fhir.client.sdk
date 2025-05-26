import json
from logging import Logger

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from tests.logger_for_test import LoggerForTest


def test_fhir_client_patient_merge() -> None:
    logger: Logger = LoggerForTest()
    test_name = "test_fhir_client_patient_merge"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text_1: list[dict[str, int]] = [{"created": 1, "updated": 0}]
    resource = {"resourceType": "Patient", "id": "12355"}
    # request_body = {"resourceType": "Bundle", "entry": [{"resource": resource}]}
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient/1/$merge",
            method="POST",
            body=json.dumps(resource),
        ),
        response=mock_response(body=json.dumps(response_text_1)),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    response: FhirMergeResponse | None = fhir_client.merge(json_data_list=[json.dumps(resource)])
    assert response is not None
    logger.info(response.responses)
    assert response.responses == response_text_1


def test_bulk_replace_with_smart_merge_false() -> None:
    logger: Logger = LoggerForTest()
    test_name = "test_bulk_replace_with_smart_merge_false"

    mock_server_url = "http://mock-server:1080"
    mock_client = MockServerFriendlyClient(base_url=mock_server_url)
    relative_url = test_name
    absolute_url = f"{mock_server_url}/{relative_url}"

    # Setup
    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    # Fixtures
    person1 = {"resourceType": "Person", "id": "1", "telecom": [{"system": "phone", "value": "123"}]}
    person1_updated = {"resourceType": "Person", "id": "1", "telecom": [{"system": "phone", "value": "456"}]}

    # Expected server-side responses
    resp1 = [{"created": True, "updated": False}]
    resp2 = [{"created": False, "updated": True}]
    resp3 = [{"created": False, "updated": True}]

    # Setup mock expectations for 3 POSTs (merge, merge, merge?smartMerge=false)
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Person/1/$merge",
            method="POST",
            body=json.dumps(person1),
        ),
        response=mock_response(body=json.dumps(resp1)),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Person/1/$merge",
            method="POST",
            body=json.dumps(person1_updated),
        ),
        response=mock_response(body=json.dumps(resp2)),
        timing=times(1),
    )

    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Person/1/$merge",
            method="POST",
            querystring={"smartMerge": ["false"]},
            body=json.dumps(person1_updated),
        ),
        response=mock_response(body=json.dumps(resp3)),
        timing=times(1),
    )

    # Initialize FHIR Client
    fhir_client = FhirClient().url(absolute_url).resource("Person")

    # Step 1: Initial merge
    response1: FhirMergeResponse | None = fhir_client.merge(json_data_list=[json.dumps(person1)])
    assert response1 is not None
    logger.info(response1.responses)
    assert response1.responses == resp1

    # Step 2: Merge updated version (e.g., adds a new phone number)
    response2: FhirMergeResponse | None = fhir_client.merge(json_data_list=[json.dumps(person1_updated)])
    assert response2 is not None
    logger.info(response2.responses)
    assert response2.responses == resp2

    # Step 3: Replace (simulate PUT)
    fhir_client_with_flag = FhirClient().url(absolute_url + "?smartMerge=false").resource("Person")
    response3: FhirMergeResponse | None = fhir_client_with_flag.merge(json_data_list=[json.dumps(person1_updated)])
    assert response3 is not None

    logger.info(response3.responses)
    assert response3.responses == resp3
