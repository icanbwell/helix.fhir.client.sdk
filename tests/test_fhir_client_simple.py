from unittest import mock
from unittest.mock import MagicMock

import requests
from requests import Session
from requests.adapters import HTTPAdapter


@mock.patch.object(Session, "get")
def test_fhir_client_simple(mocked_session: MagicMock,) -> None:
    mock_response = mocked_session.return_value

    http = requests.Session()
    adapter = HTTPAdapter()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    response = http.get("http://foo")

    assert response is mock_response
