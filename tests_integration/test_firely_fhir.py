from logging import Logger

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.logger_for_test import LoggerForTest


def test_limit_fhir_api() -> None:
    logger: Logger = LoggerForTest()
    url = "https://server.fire.ly"
    fhir_client = FhirClient()
    fhir_client = fhir_client.client_credentials(
        client_id="",
        client_secret="",
    ).auth_scopes(["user/*.read"])

    fhir_client = fhir_client.url(url).limit(3).resource("Patient")
    response: FhirGetResponse = fhir_client.get()

    logger.info(response.get_response_text())

    assert 3 == len(response.get_resources())
