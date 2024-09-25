from typing import Dict, Any, List

import aiohttp
import pytest
from aioresponses import aioresponses

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


@pytest.fixture
def graph_processor() -> FhirClient:
    """
    Fixture to create an instance of the SimulatedGraphProcessorMixin class.
    """

    class TestGraphProcessor(FhirClient):
        def __init__(self) -> None:
            super().__init__()
            self.url("http://example.com/fhir")
            self.id_("1")
            self.log_level("DEBUG")
            self.page_size(1)

        def create_http_session(self) -> aiohttp.ClientSession:
            """
            Create a mock HTTP session.
            """
            return aiohttp.ClientSession()

    return TestGraphProcessor()


@pytest.mark.asyncio
async def test_process_simulate_graph_async(
    graph_processor: SimulatedGraphProcessorMixin,
) -> None:
    """
    Test the process_simulate_graph_async method.
    """
    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [],
    }

    with aioresponses() as m:
        # Mock the HTTP GET request for the initial resource
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )

        async_gen = graph_processor.process_simulate_graph_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            concurrent_requests=1,
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=None,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        assert isinstance(response[0], FhirGetResponse)
        assert response[0].resource_type == "Patient"


@pytest.mark.asyncio
async def test_simulate_graph_async(
    graph_processor: SimulatedGraphProcessorMixin,
) -> None:
    """
    Test the simulate_graph_async method.
    """
    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [],
    }

    with aioresponses() as m:
        # Mock the HTTP GET request for the initial resource
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )

        response = await graph_processor.simulate_graph_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            concurrent_requests=1,
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
        )

        assert isinstance(response, FhirGetResponse)
        assert response.resource_type == "Patient"


@pytest.mark.asyncio
async def test_graph_definition_with_single_link(
    graph_processor: SimulatedGraphProcessorMixin,
) -> None:
    """
    Test GraphDefinition with a single link.
    """
    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [{"target": [{"type": "Observation", "params": "subject={ref}"}]}],
    }

    with aioresponses() as m:
        # Mock the HTTP GET request for the initial resource
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        # Mock the HTTP GET request for the linked resource
        m.get(
            "http://example.com/fhir/Observation?subject=1",
            payload={"resourceType": "Observation", "id": "1"},
        )

        async_gen = graph_processor.process_simulate_graph_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            concurrent_requests=1,
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=None,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: List[Dict[str, Any]] = response[0].get_resources()
        assert resources[0] == {"resourceType": "Patient", "id": "1"}
        assert resources[1] == {"resourceType": "Observation", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_nested_links(
    graph_processor: SimulatedGraphProcessorMixin,
) -> None:
    """
    Test GraphDefinition with nested links.
    """
    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {
                        "type": "Observation",
                        "params": "subject={ref}",
                        "link": [
                            {
                                "target": [
                                    {
                                        "type": "DiagnosticReport",
                                        "params": "result={ref}",
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }
        ],
    }

    with aioresponses() as m:
        # Mock the HTTP GET request for the initial resource
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        # Mock the HTTP GET request for the linked Observation
        m.get(
            "http://example.com/fhir/Observation?subject=1",
            payload={"resourceType": "Observation", "id": "1"},
        )
        # Mock the HTTP GET request for the nested DiagnosticReport
        m.get(
            "http://example.com/fhir/DiagnosticReport?result=1",
            payload={"resourceType": "DiagnosticReport", "id": "1"},
        )

        async_gen = graph_processor.process_simulate_graph_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            concurrent_requests=1,
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=None,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: List[Dict[str, Any]] = response[0].get_resources()
        assert (
            len(resources) == 3
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        assert resources[0] == {"resourceType": "Patient", "id": "1"}
        assert resources[1] == {"resourceType": "Observation", "id": "1"}
        assert resources[2] == {"resourceType": "DiagnosticReport", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_targets(
    graph_processor: SimulatedGraphProcessorMixin,
) -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {"type": "Observation", "params": "subject={ref}"},
                    {"type": "Condition", "params": "subject={ref}"},
                ]
            }
        ],
    }

    with aioresponses() as m:
        # Mock the HTTP GET request for the initial resource
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        # Mock the HTTP GET request for the linked Observation
        m.get(
            "http://example.com/fhir/Observation?subject=1",
            payload={"resourceType": "Observation", "id": "1"},
        )
        # Mock the HTTP GET request for the linked Condition
        m.get(
            "http://example.com/fhir/Condition?subject=1",
            payload={"resourceType": "Condition", "id": "1"},
        )

        async_gen = graph_processor.process_simulate_graph_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            concurrent_requests=1,
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=None,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: List[Dict[str, Any]] = response[0].get_resources()
        assert (
            len(resources) == 3
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        assert resources[0] == {"resourceType": "Patient", "id": "1"}
        assert resources[1] == {"resourceType": "Observation", "id": "1"}
        assert resources[2] == {"resourceType": "Condition", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_no_links(
    graph_processor: SimulatedGraphProcessorMixin,
) -> None:
    """
    Test GraphDefinition with no links (only the start resource).
    """
    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [],
    }

    with aioresponses() as m:
        # Mock the HTTP GET request for the initial resource
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )

        async_gen = graph_processor.process_simulate_graph_async(
            id_="1",
            graph_json=graph_json,
            contained=False,
            concurrent_requests=1,
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=None,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: List[Dict[str, Any]] = response[0].get_resources()
        assert len(resources) == 1
        assert resources[0] == {"resourceType": "Patient", "id": "1"}


@pytest.mark.asyncio
async def test_process_simulate_graph_async_multiple_patients(
    graph_processor: SimulatedGraphProcessorMixin,
) -> None:
    """
    Test processing of multiple patients.
    """
    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [],
    }

    with aioresponses() as m:
        payload = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "1"}},
                {"resource": {"resourceType": "Patient", "id": "2"}},
                {"resource": {"resourceType": "Patient", "id": "3"}},
            ],
        }
        # Mock the HTTP GET requests for multiple patient resources
        m.get("http://example.com/fhir/Patient?id=1%252C2%252C3", payload=payload)

        graph_processor.page_size(3)
        async_gen = graph_processor.process_simulate_graph_async(
            id_=["1", "2", "3"],
            graph_json=graph_json,
            contained=False,
            concurrent_requests=1,
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=None,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: List[Dict[str, Any]] = response[0].get_resources()
        assert resources[0] == {"resourceType": "Patient", "id": "1"}
        assert resources[1] == {"resourceType": "Patient", "id": "2"}
        assert resources[2] == {"resourceType": "Patient", "id": "3"}


# @pytest.mark.asyncio
# async def test_process_simulate_graph_async_multiple_patients_one_by_one(
#     graph_processor: SimulatedGraphProcessorMixin,
# ) -> None:
#     """
#     Test processing of multiple patients.
#     """
#     graph_json: Dict[str, Any] = {
#         "id": "1",
#         "name": "Test Graph",
#         "resourceType": "GraphDefinition",
#         "start": "Patient",
#         "link": [],
#     }
#
#     with aioresponses() as m:
#         # Mock the HTTP GET requests for multiple patient resources
#         m.get(
#             "http://example.com/fhir/Patient/1",
#             payload={"resourceType": "Patient", "id": "1"},
#         )
#         m.get(
#             "http://example.com/fhir/Patient/2",
#             payload={"resourceType": "Patient", "id": "2"},
#         )
#         m.get(
#             "http://example.com/fhir/Patient/3",
#             payload={"resourceType": "Patient", "id": "3"},
#         )
#
#         graph_processor.page_size(1)
#         async_gen = graph_processor.process_simulate_graph_async(
#             id_=["1", "2", "3"],
#             graph_json=graph_json,
#             contained=False,
#             concurrent_requests=1,
#             separate_bundle_resources=False,
#             restrict_to_scope=None,
#             restrict_to_resources=None,
#             restrict_to_capability_statement=None,
#             retrieve_and_restrict_to_capability_statement=None,
#             ifModifiedSince=None,
#             eTag=None,
#             logger=None,
#             url=None,
#             expand_fhir_bundle=False,
#             auth_scopes=[],
#         )
#
#         response = [r async for r in async_gen]
#         assert len(response) == 3
#         assert response[0].get_resources() == [{"resourceType": "Patient", "id": "1"}]
#
#         assert response[1].get_resources() == [{"resourceType": "Patient", "id": "2"}]
#         assert response[2].get_resources() == [{"resourceType": "Patient", "id": "3"}]
#
#
# @pytest.mark.asyncio
# async def test_process_simulate_graph_async_multiple_patients_with_links(
#     graph_processor: SimulatedGraphProcessorMixin,
# ) -> None:
#     """
#     Test processing of multiple patients with linked resources.
#     """
#     graph_json: Dict[str, Any] = {
#         "id": "1",
#         "name": "Test Graph",
#         "resourceType": "GraphDefinition",
#         "start": "Patient",
#         "link": [{"target": [{"type": "Observation", "params": "subject={ref}"}]}],
#     }
#
#     with aioresponses() as m:
#         # Mock the HTTP GET requests for multiple patient resources
#         m.get(
#             "http://example.com/fhir/Patient/1",
#             payload={"resourceType": "Patient", "id": "1"},
#         )
#         m.get(
#             "http://example.com/fhir/Patient/2",
#             payload={"resourceType": "Patient", "id": "2"},
#         )
#         m.get(
#             "http://example.com/fhir/Patient/3",
#             payload={"resourceType": "Patient", "id": "3"},
#         )
#
#         # Mock the HTTP GET requests for the linked Observation resources
#         m.get(
#             "http://example.com/fhir/Observation?subject=1",
#             payload={"resourceType": "Observation", "id": "1"},
#         )
#         m.get(
#             "http://example.com/fhir/Observation?subject=2",
#             payload={"resourceType": "Observation", "id": "2"},
#         )
#         m.get(
#             "http://example.com/fhir/Observation?subject=3",
#             payload={"resourceType": "Observation", "id": "3"},
#         )
#
#         async_gen = graph_processor.process_simulate_graph_async(
#             id_=["1", "2", "3"],
#             graph_json=graph_json,
#             contained=False,
#             concurrent_requests=1,
#             separate_bundle_resources=False,
#             restrict_to_scope=None,
#             restrict_to_resources=None,
#             restrict_to_capability_statement=None,
#             retrieve_and_restrict_to_capability_statement=None,
#             ifModifiedSince=None,
#             eTag=None,
#             logger=None,
#             url=None,
#             expand_fhir_bundle=False,
#             auth_scopes=[],
#         )
#
#         response = [r async for r in async_gen]
#         assert len(response) == 6
#         assert response[0].resource_type == "Patient"
#         assert response[1].resource_type == "Observation"
#         assert response[2].resource_type == "Patient"
#         assert response[3].resource_type == "Observation"
#         assert response[4].resource_type == "Patient"
#         assert response[5].resource_type == "Observation"
#         assert response[0].responses is not None
#         assert response[1].responses is not None
#         assert response[2].responses is not None
#         assert response[3].responses is not None
#         assert response[4].responses is not None
#         assert response[5].responses is not None
#
#
# @pytest.mark.asyncio
# async def test_simulate_graph_async_multiple_patients(
#     graph_processor: SimulatedGraphProcessorMixin,
# ) -> None:
#     """
#     Test simulate_graph_async method with multiple patients.
#     """
#     graph_json: Dict[str, Any] = {
#         "id": "1",
#         "name": "Test Graph",
#         "resourceType": "GraphDefinition",
#         "start": "Patient",
#         "link": [],
#     }
#
#     with aioresponses() as m:
#         # Mock the HTTP GET requests for multiple patient resources
#         m.get(
#             "http://example.com/fhir/Patient/1",
#             payload={"resourceType": "Patient", "id": "1"},
#         )
#         m.get(
#             "http://example.com/fhir/Patient/2",
#             payload={"resourceType": "Patient", "id": "2"},
#         )
#         m.get(
#             "http://example.com/fhir/Patient/3",
#             payload={"resourceType": "Patient", "id": "3"},
#         )
#
#         response = await graph_processor.simulate_graph_async(
#             id_=["1", "2", "3"],
#             graph_json=graph_json,
#             contained=False,
#             concurrent_requests=1,
#             separate_bundle_resources=False,
#             restrict_to_scope=None,
#             restrict_to_resources=None,
#             restrict_to_capability_statement=None,
#             retrieve_and_restrict_to_capability_statement=None,
#             ifModifiedSince=None,
#             eTag=None,
#         )
#
#         assert response.resource_type == "Patient"
#         assert response.responses is not None
#
#
# @pytest.mark.asyncio
# async def test_simulate_graph_streaming_async_multiple_patients(
#     graph_processor: SimulatedGraphProcessorMixin,
# ) -> None:
#     """
#     Test simulate_graph_streaming_async method with multiple patients.
#     """
#     graph_json: Dict[str, Any] = {
#         "id": "1",
#         "name": "Test Graph",
#         "resourceType": "GraphDefinition",
#         "start": "Patient",
#         "link": [],
#     }
#
#     with aioresponses() as m:
#         # Mock the HTTP GET requests for multiple patient resources
#         m.get(
#             "http://example.com/fhir/Patient/1",
#             payload={"resourceType": "Patient", "id": "1"},
#         )
#         m.get(
#             "http://example.com/fhir/Patient/2",
#             payload={"resourceType": "Patient", "id": "2"},
#         )
#         m.get(
#             "http://example.com/fhir/Patient/3",
#             payload={"resourceType": "Patient", "id": "3"},
#         )
#
#         async_gen = graph_processor.simulate_graph_streaming_async(
#             id_=["1", "2", "3"],
#             graph_json=graph_json,
#             contained=False,
#             concurrent_requests=1,
#             separate_bundle_resources=False,
#             restrict_to_scope=None,
#             restrict_to_resources=None,
#             restrict_to_capability_statement=None,
#             retrieve_and_restrict_to_capability_statement=None,
#             ifModifiedSince=None,
#             eTag=None,
#         )
#
#         response = [r async for r in async_gen]
#         assert len(response) == 3
#         assert response[0].resource_type == "Patient"
#         assert response[1].resource_type == "Patient"
#         assert response[2].resource_type == "Patient"
#         assert response[0].responses is not None
#         assert response[1].responses is not None
#         assert response[2].responses is not None
