from typing import Any, Dict, List, Optional

from helix_fhir_client_sdk.responses.resource_separator import ResourceSeparator


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

    result_resources_list: Dict[str, Optional[str] | List[Any]] = (
        await ResourceSeparator.separate_contained_resources_async(
            resources=resources_list,
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

    assert result_resources_list == expected_resources_list[0]
