import requests
import requests_mock


def test_fhir_client_simple() -> None:
    http = requests.Session()
    adapter = requests_mock.Adapter()
    adapter.register_uri("GET", "http://foo", text="data")

    http.mount("https://", adapter)
    http.mount("http://", adapter)
    response = http.get("http://foo")

    print(response.content)
    assert response.content == b"data"
