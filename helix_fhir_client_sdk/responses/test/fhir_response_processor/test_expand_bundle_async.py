from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)


async def test_expand_bundle_async() -> None:
    response_json = {
        "resourceType": "Bundle",
        "total": 2,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
            {"resource": {"resourceType": "Patient", "id": "2"}},
        ],
    }
    resources = ""
    total_count = 0
    access_token = "mock_access_token"
    url = "http://example.com"
    separate_bundle_resources = False
    extra_context_to_return = None

    result_resources, result_total_count = (
        await FhirResponseProcessor._expand_bundle_async(
            resources=resources,
            response_json=response_json,
            total_count=total_count,
            access_token=access_token,
            url=url,
            separate_bundle_resources=separate_bundle_resources,
            extra_context_to_return=extra_context_to_return,
        )
    )

    expected_resources = '[{"resourceType": "Patient", "id": "1"}, {"resourceType": "Patient", "id": "2"}]'
    expected_total_count = 2

    assert result_resources == expected_resources
    assert result_total_count == expected_total_count
