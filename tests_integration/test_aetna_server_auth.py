from typing import Dict

import pytest


@pytest.mark.skip("for testing")
def test_aetna_server_auth() -> None:
    import requests

    url = "https://vteapif1.aetna.com/fhirdemo/v1/patientaccess/Patient/1234567890123456701"

    payload: Dict[str, str] = {}
    headers: Dict[str, str] = {
        "Host": "vteapif1.aetna.com",
        "accept": "*/*",
        "user-agent": "curl/7.79.1",
        "Authorization": "Bearer {token}",
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    print(response.text)
    print(response.json())
    print(response.headers)
