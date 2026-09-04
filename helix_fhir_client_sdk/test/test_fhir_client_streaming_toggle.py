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


def test_use_data_streaming_overwrites_a_prior_explicit_accept_and_content_type() -> None:
    """use_data_streaming() is a deterministic last-call-wins setter, like every other
    header setter on this builder - it does not try to detect and preserve an unrelated
    explicit override, since a value-based heuristic can't distinguish "streaming set
    this" from "the caller happened to choose the same string" (e.g. a caller who sets
    .content_type("application/fhir+ndjson") directly, for reasons unrelated to
    use_data_streaming, and later calls use_data_streaming(False) expecting no effect).
    Call .accept()/.content_type() after use_data_streaming() to customize the value.
    """
    fhir_client = FhirClient().use_data_streaming(True).accept("application/xml").content_type("application/xml")

    fhir_client.use_data_streaming(False)

    assert fhir_client._accept == "application/fhir+json"
    assert fhir_client._content_type == "application/fhir+json"


def test_content_type_set_after_use_data_streaming_wins() -> None:
    fhir_client = FhirClient().use_data_streaming(True).content_type("application/xml")

    assert fhir_client._content_type == "application/xml"
