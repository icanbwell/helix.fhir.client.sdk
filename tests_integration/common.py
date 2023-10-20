from requests import get, Response


def clean_fhir_server() -> None:
    # clean the fhir server
    clean_response: Response = get("http://fhir:3000/clean")
    assert clean_response.ok, clean_response
