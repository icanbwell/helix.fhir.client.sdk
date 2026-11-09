"""DCON-6540: the URL forms that go into logs and telemetry carry no query values, resource ids or credentials."""

import pytest

from helix_fhir_client_sdk.utilities.url_redactor import UrlRedactor

BASE_URL = "http://fhir.example.test/4_0_0"


@pytest.mark.parametrize(
    "url, expected_template",
    [
        pytest.param(f"{BASE_URL}/Patient/patient-test-001", f"{BASE_URL}/Patient/{{id}}", id="read-by-id"),
        pytest.param(
            f"{BASE_URL}/Observation?patient=patient-test-001&_count=10",
            f"{BASE_URL}/Observation",
            id="search-query-values",
        ),
        pytest.param(
            f"{BASE_URL}/Patient/patient-test-001/$everything?_since=2026-01-01",
            f"{BASE_URL}/Patient/{{id}}/$everything",
            id="instance-operation",
        ),
        pytest.param(
            f"{BASE_URL}/Observation/observation-test-001/_history/2",
            f"{BASE_URL}/Observation/{{id}}/_history/{{vid}}",
            id="version-read",
        ),
        pytest.param(
            f"{BASE_URL}/Patient/patient-test-001/Observation/observation-test-001",
            f"{BASE_URL}/Patient/{{id}}/Observation/{{id}}",
            id="compartment",
        ),
        pytest.param(f"{BASE_URL}/Patient/$merge", f"{BASE_URL}/Patient/$merge", id="type-operation"),
        pytest.param(f"{BASE_URL}/Patient/_search", f"{BASE_URL}/Patient/_search", id="search-by-post"),
        pytest.param(f"{BASE_URL}/metadata", f"{BASE_URL}/metadata", id="no-resource-type"),
        pytest.param(f"{BASE_URL}?_getpages=synthetic-page-cursor-0001", BASE_URL, id="next-page-on-base-url"),
        pytest.param(f"{BASE_URL}/page/{'c' * 65}", f"{BASE_URL}/page/{{value}}", id="opaque-path-value"),
        pytest.param(
            "https://user:pw@fhir.example.test:8443/fhir/Patient/patient-test-001#section",  # pragma: allowlist secret
            "https://fhir.example.test:8443/fhir/Patient/{id}",
            id="user-info-port-and-fragment",
        ),
        pytest.param("/4_0_0/Patient/patient-test-001?_id=x", "/4_0_0/Patient/{id}", id="relative"),
    ],
)
def test_get_url_template_keeps_no_query_values_ids_or_credentials(url: str, expected_template: str) -> None:
    # Act
    template = UrlRedactor.get_url_template(url=url)

    # Assert
    assert template == expected_template


@pytest.mark.parametrize(
    "url, expected_host",
    [
        pytest.param(f"{BASE_URL}/Observation?patient=patient-test-001", "fhir.example.test", id="path-and-query"),
        pytest.param(
            "https://user:pw@FHIR.Example.Test:8443/fhir",  # pragma: allowlist secret
            "fhir.example.test",
            id="user-info-and-port",
        ),
        pytest.param("/4_0_0/Patient?_id=patient-test-001", None, id="relative"),
    ],
)
def test_get_host_returns_only_the_host_name(url: str, expected_host: str | None) -> None:
    # Act
    host = UrlRedactor.get_host(url=url)

    # Assert
    assert host == expected_host
