from types import SimpleNamespace
from typing import Dict

import aiohttp
import pytest
from aiohttp import ClientSession, TraceRequestEndParams


@pytest.mark.skip("for testing")
async def test_aetna_server_auth_aiohttp() -> None:
    # environ["AIOHTTP_NO_EXTENSIONS"] = "1"
    url = "https://vteapif1.aetna.com/fhirdemo/v1/patientaccess/Patient/1234567890123456701"

    payload: Dict[str, str] = {}
    headers: Dict[str, str] = {
        "Host": "vteapif1.aetna.com",
        "accept": "*/*",
        "user-agent": "curl/7.79.1",
        "content-type": "application/json",
        "Authorization": "Bearer {token}",
    }

    async def on_request_end(
        session: ClientSession,
        trace_config_ctx: SimpleNamespace,
        params: TraceRequestEndParams,
    ) -> None:
        print(
            "Ending %s request for %s. I sent: %s"
            % (params.method, params.url, params.headers)
        )
        print("Sent headers: %s" % params.response.request_info.headers)

    trace_config = aiohttp.TraceConfig()
    # trace_config.on_request_start.append(on_request_start)
    trace_config.on_request_end.append(on_request_end)
    # trace_config.on_response_chunk_received
    session: ClientSession = aiohttp.ClientSession(trace_configs=[trace_config])

    response = await session.get(url, headers=headers, data=payload)

    print(response.text)
    print(await response.json())
    print(response.headers)
