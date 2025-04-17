from logging import Logger

import httpx
import pytest

from tests.logger_for_test import LoggerForTest


@pytest.mark.skip("for testing")
async def test_aetna_server_auth_httpx() -> None:
    logger: Logger = LoggerForTest()
    # environ["AIOHTTP_NO_EXTENSIONS"] = "1"
    url = "https://vteapif1.aetna.com/fhirdemo/v1/patientaccess/Patient/1234567890123456701"

    # payload = {}
    headers: dict[str, str] = {
        "Host": "vteapif1.aetna.com",
        "accept": "*/*",
        "user-agent": "curl/7.79.1",
        # 'content-type': 'application/json',
        "Authorization": "Bearer {token}",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        logger.info(response.headers)
        logger.info(response.text)
        logger.info(response.json())
