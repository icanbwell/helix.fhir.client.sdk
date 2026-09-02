"""Regression tests for FhirClient.use_data_streaming()'s Accept/Content-Type bookkeeping."""

from helix_fhir_client_sdk.fhir_client import FhirClient


def test_use_data_streaming_true_sets_ndjson_accept_and_content_type() -> None:
    fhir_client = FhirClient().use_data_streaming(True)

    assert fhir_client._accept == "application/fhir+ndjson"
    assert fhir_client._content_type == "application/fhir+ndjson"


def test_use_data_streaming_false_after_true_reverts_to_json_defaults() -> None:
    fhir_client = FhirClient().use_data_streaming(True).use_data_streaming(False)

    assert fhir_client._accept == "application/fhir+json"
    assert fhir_client._content_type == "application/fhir+json"


def test_use_data_streaming_false_preserves_explicit_accept_and_content_type() -> None:
    fhir_client = (
        FhirClient()
        .use_data_streaming(True)
        .accept("application/xml")
        .content_type("application/xml")
        .use_data_streaming(False)
    )

    assert fhir_client._accept == "application/xml"
    assert fhir_client._content_type == "application/xml"
