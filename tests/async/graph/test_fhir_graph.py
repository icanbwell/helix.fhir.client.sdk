import json as json_
from typing import Any, Dict

from aioresponses import aioresponses, CallbackResult
from yarl import URL

from helix_fhir_client_sdk.async_fhir_client import AsyncFhirClient
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
    GraphDefinitionLink,
    GraphDefinitionTarget,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


async def test_async_fhir_graph() -> None:
    print("")
    mock: aioresponses
    with aioresponses() as mock:  # type: ignore
        graph_definition = GraphDefinition(
            id_="123",
            name="my_everything",
            start="Patient",
            link=[
                GraphDefinitionLink(
                    target=[
                        GraphDefinitionTarget(
                            type_="Location", params="managingOrganization={ref}"
                        )
                    ]
                ),
                GraphDefinitionLink(
                    target=[
                        GraphDefinitionTarget(
                            type_="HealthcareService",
                            params="providedBy={ref}",
                            link=[
                                GraphDefinitionLink(
                                    target=[
                                        GraphDefinitionTarget(
                                            type_="Schedule", params="actor={ref}"
                                        )
                                    ]
                                )
                            ],
                        )
                    ]
                ),
            ],
        )

        url = "http://foo"
        response_text = {"resourceType": "Patient", "id": "12355"}

        def match_request_text(
            url_: URL,
            allow_redirects: bool,
            data: bytes,
            headers: Dict[str, str],
            json: Dict[str, Any],
        ) -> CallbackResult:
            ...  # request.text may be None, or '' prevents a TypeError.
            if json == graph_definition.to_dict():
                return CallbackResult(status=200, payload=response_text)
            return CallbackResult(status=400)

        mock.post(f"{url}/Patient/1/$graph", callback=match_request_text)

        fhir_client = AsyncFhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirGetResponse = await fhir_client.graph(
            graph_definition=graph_definition, contained=False
        )

        print(response.responses)
        assert response.responses == json_.dumps(response_text)
