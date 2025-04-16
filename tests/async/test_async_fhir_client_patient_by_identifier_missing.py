import json
from logging import Logger

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.filters.property_missing_filter import PropertyMissingFilter
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.logger_for_test import LoggerForTest


async def test_async_fhir_client_patient_by_identifier_missing_false() -> None:
    logger: Logger = LoggerForTest()
    # Arrange
    test_name = "test_fhir_client_patient_by_id_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*")
    mock_client.reset()

    response_text: str = json.dumps({"resourceType": "Patient", "id": "12355"})
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={"identifier:missing": "false"},
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    # Act
    fhir_client = FhirClient()
    fhir_client = (
        fhir_client.url(absolute_url)
        .resource("Patient")
        .filter([PropertyMissingFilter(property_="identifier", missing=False)])
    )
    response: FhirGetResponse = await fhir_client.get_async()

    # Assert
    logger.info(response.get_response_text())
    assert response.get_response_text() == response_text


async def test_async_fhir_client_patient_by_identifier_missing_true() -> None:
    logger: Logger = LoggerForTest()
    # Arrange
    test_name = "test_fhir_client_patient_by_id_async"

    mock_server_url = "http://mock-server:1080"
    mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

    relative_url: str = test_name
    absolute_url: str = mock_server_url + "/" + test_name

    mock_client.clear(f"/{test_name}/*")
    mock_client.reset()

    response_text: str = json.dumps({"resourceType": "Patient", "id": "12355"})
    mock_client.expect(
        request=mock_request(
            path=f"/{relative_url}/Patient",
            method="GET",
            querystring={"identifier:missing": "true"},
        ),
        response=mock_response(body=response_text),
        timing=times(1),
    )

    # Act
    fhir_client = FhirClient()
    fhir_client = (
        fhir_client.url(absolute_url)
        .resource("Patient")
        .filter([PropertyMissingFilter(property_="identifier", missing=True)])
    )
    response: FhirGetResponse = await fhir_client.get_async()

    # Assert
    logger.info(response.get_response_text())
    assert response.get_response_text() == response_text
