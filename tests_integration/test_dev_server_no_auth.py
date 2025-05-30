from logging import Logger

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.logger_for_test import LoggerForTest


@pytest.mark.skip("for talking to production")
def test_dev_server_no_auth() -> None:
    logger: Logger = LoggerForTest()
    url = "http://fhir:3000/4_0_0"
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Patient")
    response: FhirGetResponse = fhir_client.get()
    logger.info(response.get_response_text())
