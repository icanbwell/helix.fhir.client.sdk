from typing import Any, Dict, List, Optional

from helix_fhir_client_sdk.responses.resource_separator import ResourceSeparator


async def test_separate_contained_resources_async_with_contained() -> None:
    resources_list: List[Dict[str, Any]] = [
        {
            "resourceType": "Patient",
            "id": "1",
            "contained": [
                {"resourceType": "Observation", "id": "obs1"},
                {"resourceType": "Medication", "id": "med1"},
            ],
        }
    ]
    access_token = "mock_access_token"
    url = "http://example.com"
    extra_context_to_return = {"extra_key": "extra_value"}

    result = await ResourceSeparator.separate_contained_resources_async(
        resources=resources_list,
        access_token=access_token,
        url=url,
        extra_context_to_return=extra_context_to_return,
    )

    expected_result = [
        {
            "observation": [{"resourceType": "Observation", "id": "obs1"}],
            "medication": [{"resourceType": "Medication", "id": "med1"}],
            "patient": [{"id": "1", "resourceType": "Patient"}],
            "token": access_token,
            "url": url,
            "extra_key": "extra_value",
        }
    ]

    assert result.resources_dicts == expected_result
    assert result.total_count == 3


async def test_separate_contained_resources_async_with_multiple_contained() -> None:
    resources_list: List[Dict[str, Any]] = [
        {
            "resourceType": "Patient",
            "id": "1",
            "contained": [
                {"resourceType": "Observation", "id": "obs1"},
                {"resourceType": "Medication", "id": "med1"},
                {"resourceType": "Observation", "id": "obs2"},
            ],
        }
    ]
    access_token = "mock_access_token"
    url = "http://example.com"
    extra_context_to_return = {"extra_key": "extra_value"}

    result = await ResourceSeparator.separate_contained_resources_async(
        resources=resources_list,
        access_token=access_token,
        url=url,
        extra_context_to_return=extra_context_to_return,
    )

    expected_result = [
        {
            "extra_key": "extra_value",
            "medication": [{"id": "med1", "resourceType": "Medication"}],
            "observation": [
                {"id": "obs1", "resourceType": "Observation"},
                {"id": "obs2", "resourceType": "Observation"},
            ],
            "patient": [{"id": "1", "resourceType": "Patient"}],
            "token": "mock_access_token",
            "url": "http://example.com",
        }
    ]

    assert result.resources_dicts == expected_result
    assert result.total_count == 4


async def test_separate_contained_resources_async_without_contained() -> None:
    resources_list: List[Dict[str, Any]] = [
        {"resourceType": "Patient", "id": "1"},
        {"resourceType": "Practitioner", "id": "2"},
    ]
    access_token = "mock_access_token"
    url = "http://example.com"
    extra_context_to_return = {"extra_key": "extra_value"}

    result = await ResourceSeparator.separate_contained_resources_async(
        resources=resources_list,
        access_token=access_token,
        url=url,
        extra_context_to_return=extra_context_to_return,
    )

    expected_result = [
        {
            "token": access_token,
            "url": url,
            "extra_key": "extra_value",
            "patient": [{"id": "1", "resourceType": "Patient"}],
        },
        {
            "token": access_token,
            "url": url,
            "extra_key": "extra_value",
            "practitioner": [{"id": "2", "resourceType": "Practitioner"}],
        },
    ]

    assert result.resources_dicts == expected_result
    assert result.total_count == 2


async def test_separate_contained_resources_async_empty_list() -> None:
    resources_list: List[Dict[str, Any]] = []
    access_token = "mock_access_token"
    url = "http://example.com"
    extra_context_to_return = {"extra_key": "extra_value"}

    result = await ResourceSeparator.separate_contained_resources_async(
        resources=resources_list,
        access_token=access_token,
        url=url,
        extra_context_to_return=extra_context_to_return,
    )

    expected_result: List[Dict[str, Optional[str] | List[Dict[str, Any]]]] = []

    assert result.resources_dicts == expected_result
    assert result.total_count == 0
