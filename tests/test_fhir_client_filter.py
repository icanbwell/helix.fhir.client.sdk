import json
from typing import Any, Dict, List, Optional

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    times,
    mock_request,
    mock_response,
)

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient
from helix_fhir_client_sdk.filters.identifier_filter import IdentifierFilter
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_filter() -> None:
    test_name = "test_mock_server"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    mock_client.expect(
        mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_count": "10",
                "_getpagesoffset": "0",
                "_total": "accurate",
                "identifier": "http://hl7.org/fhir/sid/us-npi|1487831681",
            },
        ),
        mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 2,
                    "entry": [{"resource": {"resourceType": "Patient", "id": "1"}}],
                }
            )
        ),
        timing=times(1),
    )

    mock_client.expect(
        mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_count": "10",
                "_getpagesoffset": "1",
                "_total": "accurate",
                "identifier": "http://hl7.org/fhir/sid/us-npi|1487831681",
            },
        ),
        mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 2,
                    "entry": [{"resource": {"resourceType": "Patient", "id": "2"}}],
                }
            )
        ),
        timing=times(1),
    )

    # mock running out of resources
    mock_client.expect(
        mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_count": "10",
                "_getpagesoffset": "2",
                "_total": "accurate",
                "identifier": "http://hl7.org/fhir/sid/us-npi|1487831681",
            },
        ),
        mock_response(
            body=json.dumps({"resourceType": "Bundle", "total": 2, "entry": []})
        ),
        timing=times(1),
    )

    fhir_client = AsyncFhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.page_size(10)
    fhir_client = fhir_client.include_total(True)
    fhir_client = fhir_client.filter(
        [IdentifierFilter(system="http://hl7.org/fhir/sid/us-npi", value="1487831681")]
    )

    def handle_batch(x: Optional[List[Dict[str, Any]]]) -> bool:
        if x:
            resources_list.extend(x)
        return True

    resources_list: List[Dict[str, Any]] = []
    response: FhirGetResponse = fhir_client.get_in_batches(fn_handle_batch=handle_batch)

    print(response.responses)
    assert response.responses == "[]"

    assert response.total_count == 2

    print(resources_list)
    # assert resources_list == [
    #     response_text_1["entry"][0]["resource"],  # type: ignore
    #     response_text_2["entry"][0]["resource"],  # type: ignore
    # ]

    mock_client.verify_expectations(test_name=test_name)
