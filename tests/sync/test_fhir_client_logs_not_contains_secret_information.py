import json
import unittest
from collections.abc import Mapping
from logging import Logger
from typing import Any

from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse

log_output = []


class TestLoggerLogs(Logger):
    """
    Logger class to mock logger and add the logs to log_output
    """

    def info(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """
        Handle messages at INFO level
        """
        log_output.append(msg)


class TestRemoveSecretInformationFromLogs(unittest.TestCase):
    """
    Test class to test secret information getting removed from the logs
    """

    def test_client_secrets_removed_from_logs(self) -> None:
        """
        Method to test secret information getting removed from the logs
        """
        test_name = "test_client_secrets_removed_from_logs"
        logger = TestLoggerLogs("test_logger")
        mock_server_url = "http://mock-server:1080"
        mock_client: MockServerFriendlyClient = MockServerFriendlyClient(base_url=mock_server_url)

        relative_url: str = test_name
        absolute_url: str = mock_server_url + "/" + test_name

        mock_client.clear(f"/{test_name}/*.*")
        mock_client.reset()

        response_text: str = json.dumps({"resourceType": "Patient", "id": "12355"})
        mock_client.expect(
            request=mock_request(path=f"/{relative_url}/Patient/12355", method="GET"),
            response=mock_response(body=response_text),
            timing=times(1),
        )

        fhir_client = FhirClient()
        fhir_client.logger(logger=logger)
        fhir_client._log_level = "DEBUG"
        fhir_client = fhir_client.url(absolute_url).resource("Patient").id_("12355")
        response: FhirGetResponse = fhir_client.get()

        assert response.get_response_text() == response_text
        self.assertNotIn("_login_token", str(log_output))
        self.assertNotIn("_access_token", str(log_output))
