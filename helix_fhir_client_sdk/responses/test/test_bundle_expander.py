from helix_fhir_client_sdk.responses.bundle_expander import (
    BundleExpander,
    BundleExpanderResult,
)


async def test_bundle_expander() -> None:
    response_json = {
        "resourceType": "Bundle",
        "total": 2,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "1"}},
            {"resource": {"resourceType": "Patient", "id": "2"}},
        ],
    }
    total_count = 0

    bundle_expander_result: BundleExpanderResult = await BundleExpander.expand_bundle_async(
        bundle=response_json,
        total_count=total_count,
    )

    expected_resources = [
        {"resourceType": "Patient", "id": "1"},
        {"resourceType": "Patient", "id": "2"},
    ]
    expected_total_count = 2

    assert bundle_expander_result.resources == expected_resources
    assert bundle_expander_result.total_count == expected_total_count
