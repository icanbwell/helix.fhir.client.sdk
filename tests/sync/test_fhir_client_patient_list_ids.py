import json
from typing import List

from mockserver_client.mockserver_client import (
    mock_request,
    mock_response,
    times,
    MockServerFriendlyClient,
)

from helix_fhir_client_sdk.fhir_client import FhirClient


def test_fhir_client_patient_list_ids() -> None:
    test_name = "test_fhir_client_patient_list_ids"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    response_text: str = json.dumps(
        [
            {"resourceType": "Patient", "id": "12355"},
            {"resourceType": "Patient", "id": "5555"},
        ]
    )
    mock_client.expect(
        mock_request(path=f"/{relative_url}/Patient", method="GET"),
        mock_response(body=response_text),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    list_of_ids: List[str] = fhir_client.get_ids_for_query()

    print(json.dumps(list_of_ids))
    assert list_of_ids == ["12355", "5555"]
