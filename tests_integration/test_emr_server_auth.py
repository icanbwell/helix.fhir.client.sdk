from datetime import UTC, datetime
from logging import Logger

import pytest

from tests.logger_for_test import LoggerForTest


@pytest.mark.skip("for testing")
def test_emr_server_auth() -> None:
    import requests

    patient_id = ""
    url = f"https://epicproxy.et1131.epichosted.com/FHIRProxy/api/FHIR/R4/AllergyIntolerance?patient={patient_id}&date=ge2024-01-01"

    token = ""

    # Convert 2024-01-01 to HTTP header date format
    modified_since_date = datetime(2024, 1, 1, tzinfo=UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")

    payload: dict[str, str] = {}
    headers: dict[str, str] = {
        "Host": "epicproxy.et1131.epichosted.com",
        "accept": "application/fhir+json",
        "user-agent": "curl/7.79.1",
        "Authorization": f"Bearer {token}",
        "If-Modified-Since": modified_since_date,
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    logger: Logger = LoggerForTest()
    logger.info(response.text)
    # logger.info(response.json())
    logger.info(response.headers)
