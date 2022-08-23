from typing import Dict, Any, List

# noinspection PyPackageRequirements
from requests import get, Response


def clean_fhir_server() -> None:
    # clean the fhir server
    clean_response: Response = get("http://fhir:3000/clean")
    assert clean_response.ok, clean_response
    has_data: bool = True
    while has_data:
        stats_response: Response = get("http://fhir:3000/stats")
        assert stats_response.ok
        stats_result: Dict[str, Any] = stats_response.json()
        # confirm all tables are at 0
        stats_collections: List[Dict[str, Any]] = stats_result["collections"]
        has_data = False
        collection: Dict[str, Any]
        for collection in stats_collections:
            if collection["count"] != 0:
                has_data = True
