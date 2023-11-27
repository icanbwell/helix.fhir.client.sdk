import json
from typing import Any, Dict, List, Optional

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient


async def test_fhir_client_patient_list_in_batches_async() -> None:
    test_name = "test_fhir_client_patient_list_in_batches_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(
        base_url=mock_server_url
    )

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    # this is the first call made by the first concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "1",
                "_getpagesoffset": "0",
                "_total": "accurate",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 2,
                    "entry": [{"resource": {"id": "1"}}],
                }
            )
        ),
        timing=times(1),
    )

    # this is the second call made by first concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "1",
                "_getpagesoffset": "3",
                "_total": "accurate",
                "id:above": "1",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 2,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    # this is the first call made by the second concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "1",
                "_getpagesoffset": "1",
                "_total": "accurate",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 2,
                    "entry": [{"resource": {"id": "2"}}],
                }
            )
        ),
        timing=times(1),
    )

    # this is the second call made by second concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "1",
                "_getpagesoffset": "3",
                "_total": "accurate",
                "id:above": "2",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 2,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    # this is the call made by the third concurrent request
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "_elements": "id",
                "_count": "1",
                "_getpagesoffset": "2",
                "_total": "accurate",
            },
        ),
        response=mock_response(
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "total": 2,
                    "entry": [],
                }
            )
        ),
        timing=times(1),
    )

    # now mock the actual calls to get resources
    response_text_1: Dict[str, Any] = {
        "resourceType": "Bundle",
        "total": 2,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
            {"resource": {"resourceType": "Patient", "id": "2"}},
        ],
    }
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={
                "id": "1,2",
                "_count": "1",
                "_getpagesoffset": "0",
                "_total": "accurate",
            },
        ),
        response=mock_response(body=json.dumps(response_text_1)),
        timing=times(1),
    )

    fhir_client = FhirClient()
    fhir_client = fhir_client.url(absolute_url).resource("Patient")
    fhir_client = fhir_client.page_size(10)
    fhir_client = fhir_client.include_total(True)

    async def handle_batch(
        resources_: List[Dict[str, Any]], page_number: Optional[int]
    ) -> bool:
        if resources_:
            resources_list.extend(resources_)
        return True

    resources_list: List[Dict[str, Any]] = []
    response: List[Dict[str, Any]] = await fhir_client.get_resources_by_query_async(
        fn_handle_batch=handle_batch,
        page_size_for_retrieving_ids=1,
        page_size_for_retrieving_resources=2,
        concurrent_requests=3,
    )

    print(response)
    assert response == []

    assert len(resources_list) == 2

    print(resources_list)
    assert resources_list == [
        {"resourceType": "Patient", "id": "1"},
        {"resourceType": "Patient", "id": "2"},
    ]

    # can't do this since we implement early stopping which is not deterministic since we use concurrent requests
    # so some calls may not be made if a concurrent call returns empty
    # mock_client.verify_expectations(test_name=test_name)
