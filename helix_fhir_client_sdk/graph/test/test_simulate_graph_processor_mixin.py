from typing import Dict, Any, List, Optional, cast

import aiohttp
import pytest
from aioresponses import aioresponses

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.test_logger import TestLogger


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


def get_graph_processor(*, max_concurrent_requests: Optional[int] = None) -> FhirClient:
    """
    Fixture to create an instance of the SimulatedGraphProcessorMixin class.
    """
    processor: FhirClient = TestGraphProcessor()
    processor = cast(
        FhirClient, processor.set_max_concurrent_requests(max_concurrent_requests)
    )
    return processor


@pytest.mark.asyncio
async def test_process_simulate_graph_async() -> None:
    """
    Test the process_simulate_graph_async method.
    """

    logger: FhirLogger = TestLogger()

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        assert isinstance(response[0], FhirGetResponse)
        assert response[0].resource_type == "Patient"


@pytest.mark.asyncio
async def test_simulate_graph_async() -> None:
    """
    Test the simulate_graph_async method.
    """

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

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
async def test_graph_definition_with_single_link() -> None:
    """
    Test GraphDefinition with a single link.
    """

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: FhirLogger = TestLogger()

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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: List[Dict[str, Any]] = response[0].get_resources()
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation == {"resourceType": "Observation", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_nested_links() -> None:
    """
    Test GraphDefinition with nested links.
    """

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: FhirLogger = TestLogger()

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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
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
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "DiagnosticReport"][0]
        assert condition == {"resourceType": "DiagnosticReport", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_links() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: FhirLogger = TestLogger()

    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {"type": "Observation", "params": "subject={ref}"},
                ]
            },
            {
                "target": [
                    {"type": "Condition", "params": "subject={ref}"},
                ]
            },
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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
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
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "Condition"][0]
        assert condition == {"resourceType": "Condition", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_targets() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: FhirLogger = TestLogger()

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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
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
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "Condition"][0]
        assert condition == {"resourceType": "Condition", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_no_links() -> None:
    """
    Test GraphDefinition with no links (only the start resource).
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: FhirLogger = TestLogger()

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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
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
async def test_process_simulate_graph_async_multiple_patients() -> None:
    """
    Test processing of multiple patients.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: FhirLogger = TestLogger()

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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
            url=None,
            expand_fhir_bundle=False,
            auth_scopes=[],
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: List[Dict[str, Any]] = response[0].get_resources()
        patient = [
            r for r in resources if r["resourceType"] == "Patient" and r["id"] == "1"
        ][0]
        assert patient == {"resourceType": "Patient", "id": "1"}
        patient = [
            r for r in resources if r["resourceType"] == "Patient" and r["id"] == "2"
        ][0]
        assert patient == {"resourceType": "Patient", "id": "2"}
        patient = [
            r for r in resources if r["resourceType"] == "Patient" and r["id"] == "3"
        ][0]
        assert patient == {"resourceType": "Patient", "id": "3"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_links_concurrent_requests() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=3
    )

    logger: FhirLogger = TestLogger()

    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {"type": "Observation", "params": "subject={ref}"},
                ]
            },
            {
                "target": [
                    {"type": "Condition", "params": "subject={ref}"},
                ]
            },
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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
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
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "Condition"][0]
        assert condition == {"resourceType": "Condition", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_targets_concurrent_requests() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=3
    )

    logger: FhirLogger = TestLogger()

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
            separate_bundle_resources=False,
            restrict_to_scope=None,
            restrict_to_resources=None,
            restrict_to_capability_statement=None,
            retrieve_and_restrict_to_capability_statement=None,
            ifModifiedSince=None,
            eTag=None,
            logger=logger,
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
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "Condition"][0]
        assert condition == {"resourceType": "Condition", "id": "1"}
