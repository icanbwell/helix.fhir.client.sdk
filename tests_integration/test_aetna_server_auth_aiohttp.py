from logging import Logger
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import ClientSession, TraceRequestEndParams

from tests.logger_for_test import LoggerForTest


@pytest.mark.skip("for testing")
async def test_aetna_server_auth_aiohttp() -> None:
    logger: Logger = LoggerForTest()
    # environ["AIOHTTP_NO_EXTENSIONS"] = "1"
    url = "https://vteapif1.aetna.com/fhirdemo/v1/patientaccess/Patient/1234567890123456701"

    payload: dict[str, str] = {}
    headers: dict[str, str] = {
        "Host": "vteapif1.aetna.com",
        "accept": "*/*",
        "user-agent": "curl/7.79.1",
        "content-type": "application/json",
        "Authorization": "Bearer {token}",
    }

    # noinspection PyShadowingNames
    async def on_request_end(
        session: ClientSession,
        trace_config_ctx: SimpleNamespace,
        params: TraceRequestEndParams,
    ) -> None:
        logger.info(f"Ending {params.method} request for {params.url}. I sent: {params.headers}")
        logger.info(f"Sent headers: {params.response.request_info.headers}")

    trace_config = aiohttp.TraceConfig()
    # trace_config.on_request_start.append(on_request_start)
    trace_config.on_request_end.append(on_request_end)
    # trace_config.on_response_chunk_received
    session: ClientSession = aiohttp.ClientSession(trace_configs=[trace_config])

    response = await session.get(url, headers=headers, data=payload)

    logger.info(response.text)
    logger.info(await response.json())
    logger.info(response.headers)
