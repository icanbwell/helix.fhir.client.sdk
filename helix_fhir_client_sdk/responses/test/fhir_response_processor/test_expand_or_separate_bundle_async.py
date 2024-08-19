from helix_fhir_client_sdk.responses.fhir_response_processor import (
    FhirResponseProcessor,
)


async def test_expand_or_separate_bundle_async() -> None:
    response_json = {
        "resourceType": "Bundle",
        "total": 2,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
            {"resource": {"resourceType": "Patient", "id": "2"}},
        ],
    }
    resources_json = ""
    total_count = 0
    access_token = "mock_access_token"
    url = "http://example.com"
    expand_fhir_bundle = True
    separate_bundle_resources = False
    extra_context_to_return = None

    result_resources_json, result_total_count = (
        await FhirResponseProcessor.expand_or_separate_bundle_async(
            access_token=access_token,
            expand_fhir_bundle=expand_fhir_bundle,
            extra_context_to_return=extra_context_to_return,
            resource_or_bundle=response_json,
            separate_bundle_resources=separate_bundle_resources,
            total_count=total_count,
            url=url,
        )
    )

    expected_resources_json = '[{"resourceType": "Patient", "id": "1"}, {"resourceType": "Patient", "id": "2"}]'
    expected_total_count = 2

    assert result_resources_json == expected_resources_json
    assert result_total_count == expected_total_count
