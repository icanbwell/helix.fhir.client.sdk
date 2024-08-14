from typing import Any, Dict, List

from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)


async def test_separate_contained_resources_async() -> None:
    entry = {
        "resource": {
            "resourceType": "Patient",
            "id": "1",
            "contained": [
                {"resourceType": "Observation", "id": "obs1"},
                {"resourceType": "Observation", "id": "obs2"},
            ],
        }
    }
    resources_list: List[Dict[str, Any]] = []
    access_token = "mock_access_token"
    url = "http://example.com"
    extra_context_to_return = {"extra_key": "extra_value"}

    result_resources_list = (
        await FhirResponseProcessor._separate_contained_resources_async(
            entry=entry,
            resources_list=resources_list,
            access_token=access_token,
            url=url,
            extra_context_to_return=extra_context_to_return,
        )
    )

    expected_resources_list = [
        {
            "patient": [{"resourceType": "Patient", "id": "1"}],
            "observation": [
                {"resourceType": "Observation", "id": "obs1"},
                {"resourceType": "Observation", "id": "obs2"},
            ],
            "token": access_token,
            "url": url,
            "extra_key": "extra_value",
        }
    ]

    assert result_resources_list == expected_resources_list
