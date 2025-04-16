from logging import Logger

import pytest

from tests.logger_for_test import LoggerForTest


@pytest.mark.skip("for testing")
def test_aetna_server_auth() -> None:
    logger: Logger = LoggerForTest()
    import requests

    url = "https://vteapif1.aetna.com/fhirdemo/v1/patientaccess/Patient/1234567890123456701"

    payload: dict[str, str] = {}
    headers: dict[str, str] = {
        "Host": "vteapif1.aetna.com",
        "accept": "*/*",
        "user-agent": "curl/7.79.1",
        "Authorization": "Bearer {token}",
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    logger.info(response.text)
    logger.info(response.json())
    logger.info(response.headers)
