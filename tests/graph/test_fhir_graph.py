import json
from typing import Any

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph.graph_definition import (
    GraphDefinition,
    GraphDefinitionLink,
    GraphDefinitionTarget,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_graph() -> None:
    print("")
    with requests_mock.Mocker() as mock:
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

        def match_request_text(request: Any) -> bool:
            ...  # request.text may be None, or '' prevents a TypeError.
            return request.text == json.dumps(graph_definition.to_dict())  # type: ignore

        mock.post(
            f"{url}/Patient/1/$graph",
            additional_matcher=match_request_text,
            json=response_text,
        )

        fhir_client = FhirClient()
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirGetResponse = fhir_client.graph(
            graph_definition=graph_definition, contained=False
        )

        print(response.responses)
        assert response.responses == json.dumps(response_text)
