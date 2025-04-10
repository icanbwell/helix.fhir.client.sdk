import asyncio
import json
import logging
from logging import Logger
from typing import Dict, Any, Optional, cast, Callable, Awaitable
from datetime import datetime

import aiohttp
import pytest
from aioresponses import aioresponses, CallbackResult

from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.function_types import RefreshTokenResult
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from logging import Logger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.logger_for_test import LoggerForTest


class TestGraphProcessor(FhirClient):
    def __init__(self) -> None:
        super().__init__()
        # noinspection HttpUrlsUsage
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


def get_payload_function(
    payload: Dict[str, Any],
    delay: int = 0,
    status: int = 200,
    match_access_token: Optional[str] = None,
) -> Callable[[str, Any], Awaitable[CallbackResult]]:
    """
    This function returns a function that will return a delayed response with the given payload.

    :param payload: The payload to return in the response.
    :param delay: The delay in seconds before returning the response.
    :param status: The status code to return in the response.
    :param match_access_token: The access token that must be matched in the request.
    :return: The function that will return the delayed response.
    """

    # noinspection PyUnusedLocal
    async def delayed_response(url: str, **kwargs: Any) -> CallbackResult:
        logger: Logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.info(f"Mock Request Received: {url}")
        if match_access_token:
            access_token = (
                kwargs.get("headers", {})
                .get("Authorization", "")
                .replace("Bearer ", "")
            )
            if access_token != match_access_token:
                await asyncio.sleep(delay)  # 2 second delay
                return CallbackResult(
                    status=401,
                    headers={},
                    body=json.dumps(
                        {
                            "error": f"Unauthorized: Unexpected access token: {access_token}"
                        }
                    ),
                )

        await asyncio.sleep(delay)  # 2 second delay
        logger.info(f"Mock Response Sent: {url}")
        return CallbackResult(
            status=status,
            headers={},
            body=json.dumps(payload),
        )

    return delayed_response  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_process_simulate_graph_async() -> None:
    """
    Test the process_simulate_graph_async method.
    """

    logger: Logger = LoggerForTest()

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
            max_concurrent_tasks=None,
            sort_resources=True,
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

    logger: Logger = LoggerForTest()

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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation.dict() == {"resourceType": "Observation", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_nested_links() -> None:
    """
    Test GraphDefinition with nested links.
    """

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: Logger = LoggerForTest()

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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        assert (
            len(resources) == 3
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation.dict() == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "DiagnosticReport"][0]
        assert condition.dict() == {"resourceType": "DiagnosticReport", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_links() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: Logger = LoggerForTest()

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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)
        assert (
            len(resources) == 3
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation.dict() == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "Condition"][0]
        assert condition.dict() == {"resourceType": "Condition", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_targets() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: Logger = LoggerForTest()

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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        assert (
            len(resources) == 3
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation.dict() == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "Condition"][0]
        assert condition.dict() == {"resourceType": "Condition", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_no_links() -> None:
    """
    Test GraphDefinition with no links (only the start resource).
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: Logger = LoggerForTest()

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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        assert len(resources) == 1
        assert resources[0].dict() == {"resourceType": "Patient", "id": "1"}


@pytest.mark.asyncio
async def test_process_simulate_graph_async_multiple_patients() -> None:
    """
    Test processing of multiple patients.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=1
    )

    logger: Logger = LoggerForTest()

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
        m.get("http://example.com/fhir/Patient?_id=1%252C2%252C3", payload=payload)

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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        patient = [
            r for r in resources if r["resourceType"] == "Patient" and r["id"] == "1"
        ][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        patient = [
            r for r in resources if r["resourceType"] == "Patient" and r["id"] == "2"
        ][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "2"}
        patient = [
            r for r in resources if r["resourceType"] == "Patient" and r["id"] == "3"
        ][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "3"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_links_concurrent_requests() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=3
    )

    logger: Logger = LoggerForTest()

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
            callback=get_payload_function({"resourceType": "Patient", "id": "1"}),
        )
        # Mock the HTTP GET request for the linked Observation
        m.get(
            "http://example.com/fhir/Observation?subject=1",
            callback=get_payload_function({"resourceType": "Observation", "id": "1"}),
        )
        # Mock the HTTP GET request for the linked Condition
        m.get(
            "http://example.com/fhir/Condition?subject=1",
            callback=get_payload_function({"resourceType": "Condition", "id": "1"}),
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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        assert (
            len(resources) == 3
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation.dict() == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "Condition"][0]
        assert condition.dict() == {"resourceType": "Condition", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_targets_concurrent_requests() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=3
    )

    logger: Logger = LoggerForTest()

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
            callback=get_payload_function({"resourceType": "Patient", "id": "1"}),
        )
        # Mock the HTTP GET request for the linked Observation
        m.get(
            "http://example.com/fhir/Observation?subject=1",
            callback=get_payload_function({"resourceType": "Observation", "id": "1"}),
        )
        # Mock the HTTP GET request for the linked Condition
        m.get(
            "http://example.com/fhir/Condition?subject=1",
            callback=get_payload_function({"resourceType": "Condition", "id": "1"}),
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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        assert (
            len(resources) == 3
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation.dict() == {"resourceType": "Observation", "id": "1"}
        condition = [r for r in resources if r["resourceType"] == "Condition"][0]
        assert condition.dict() == {"resourceType": "Condition", "id": "1"}


@pytest.mark.asyncio
async def test_graph_definition_with_nested_links_concurrent_requests() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(
        max_concurrent_requests=3
    )

    logger: Logger = LoggerForTest()

    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {
                        "type": "Encounter",
                        "params": "patient={ref}",
                        "link": [
                            {
                                "path": "participant.individual[x]",
                                "target": [{"type": "Practitioner"}],
                            },
                            {
                                "path": "location.location[x]",
                                "target": [{"type": "Location"}],
                            },
                            {
                                "path": "serviceProvider",
                                "target": [{"type": "Organization"}],
                            },
                        ],
                    }
                ]
            },
        ],
    }

    with aioresponses() as m:
        # Mock the HTTP GET request for the initial resource
        m.get(
            "http://example.com/fhir/Patient/1",
            callback=get_payload_function({"resourceType": "Patient", "id": "1"}),
        )
        # Mock the HTTP GET request for the linked Observation
        m.get(
            "http://example.com/fhir/Encounter?patient=1",
            callback=get_payload_function(
                {
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "8",
                                "participant": [
                                    {"individual": {"reference": "Practitioner/12345"}}
                                ],
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "10",
                                "participant": [
                                    {"individual": {"reference": "Practitioner/12345"}}
                                ],
                            }
                        },
                    ]
                }
            ),
        )

        m.get(
            "http://example.com/fhir/Practitioner/12345",
            callback=get_payload_function(
                {"resourceType": "Practitioner", "id": "12345"}
            ),
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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1

        m.assert_any_call(url="http://example.com/fhir/Patient/1")
        m.assert_any_call(url="http://example.com/fhir/Encounter?patient=1")
        m.assert_any_call(url="http://example.com/fhir/Practitioner/12345")

        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        assert (
            len(resources) == 4
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        encounter = [
            r for r in resources if r["resourceType"] == "Encounter" and r["id"] == "8"
        ][0]
        assert encounter.dict() == {
            "resourceType": "Encounter",
            "id": "8",
            "participant": [{"individual": {"reference": "Practitioner/12345"}}],
        }
        encounter = [
            r for r in resources if r["resourceType"] == "Encounter" and r["id"] == "10"
        ][0]
        assert encounter.dict() == {
            "resourceType": "Encounter",
            "id": "10",
            "participant": [{"individual": {"reference": "Practitioner/12345"}}],
        }
        condition = [r for r in resources if r["resourceType"] == "Practitioner"][0]
        assert condition.dict() == {"resourceType": "Practitioner", "id": "12345"}


@pytest.mark.asyncio
async def test_process_simulate_graph_401_patient_only_async() -> None:
    """
    Test the process_simulate_graph_async method.
    """

    logger: Logger = LoggerForTest()

    graph_processor: FhirClient = get_graph_processor(max_concurrent_requests=1)

    graph_processor.set_log_all_response_urls(True)

    graph_processor.set_access_token("old_access_token")

    # noinspection PyUnusedLocal
    async def my_refresh_token_function(
        url: Optional[str],
        status_code: Optional[int],
        current_token: Optional[str],
        expiry_date: Optional[datetime],
        retry_count: Optional[int],
    ) -> RefreshTokenResult:
        return RefreshTokenResult(
            access_token="new_access_token", expiry_date=None, abort_request=False
        )

    graph_processor.refresh_token_function(my_refresh_token_function)

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
            url="http://example.com/fhir/Patient/1",
            callback=get_payload_function(
                {
                    "resourceType": "OperationOutcome",
                    "issue": [
                        {
                            "severity": "error",
                            "code": "forbidden",
                            "details": {"text": "Unauthorized access"},
                        }
                    ],
                },
                status=401,
                match_access_token="old_access_token",
            ),
        )
        m.get(
            "http://example.com/fhir/Patient/1",
            callback=get_payload_function(
                {"resourceType": "Patient", "id": "1"},
                match_access_token="new_access_token",
            ),
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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        assert isinstance(response[0], FhirGetResponse)
        assert response[0].resource_type == "Patient"
        assert response[0].access_token == "new_access_token"
        assert response[0].results_by_url is not None
        assert len(response[0].results_by_url) == 2
        assert [
            dict(
                status_code=r.status_code,
                url=r.url,
            )
            for r in response[0].results_by_url
        ] == [
            {
                "status_code": 401,
                "url": "http://example.com/fhir/Patient/1",
            },
            {
                "status_code": 200,
                "url": "http://example.com/fhir/Patient/1",
            },
        ]


@pytest.mark.asyncio
async def test_graph_definition_with_single_link_401() -> None:
    """
    Test GraphDefinition with a single link.
    """

    graph_processor: FhirClient = get_graph_processor(max_concurrent_requests=1)

    graph_processor.set_log_all_response_urls(True)

    graph_processor.set_access_token("old_access_token")

    # noinspection PyUnusedLocal
    async def my_refresh_token_function(
        url: Optional[str],
        status_code: Optional[int],
        current_token: Optional[str],
        expiry_date: Optional[datetime],
        retry_count: Optional[int],
    ) -> RefreshTokenResult:
        return RefreshTokenResult(
            access_token="new_access_token", expiry_date=None, abort_request=False
        )

    graph_processor.refresh_token_function(my_refresh_token_function)

    logger: Logger = LoggerForTest()

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
            callback=get_payload_function(
                {
                    "resourceType": "OperationOutcome",
                    "issue": [
                        {
                            "severity": "error",
                            "code": "forbidden",
                            "details": {"text": "Unauthorized access"},
                        }
                    ],
                },
                status=401,
                match_access_token="old_access_token",
            ),
        )
        m.get(
            "http://example.com/fhir/Patient/1",
            callback=get_payload_function(
                {"resourceType": "Patient", "id": "1"},
                match_access_token="new_access_token",
            ),
        )
        # Mock the HTTP GET request for the linked resource
        m.get(
            "http://example.com/fhir/Observation?subject=1",
            callback=get_payload_function(
                {"resourceType": "Observation", "id": "1"},
                match_access_token="new_access_token",
            ),
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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1
        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        observation = [r for r in resources if r["resourceType"] == "Observation"][0]
        assert observation.dict() == {"resourceType": "Observation", "id": "1"}

        assert response[0].access_token == "new_access_token"
        assert response[0].results_by_url is not None

        assert [
            dict(
                status_code=r.status_code,
                url=r.url,
            )
            for r in response[0].results_by_url
        ] == [
            {
                "status_code": 401,
                "url": "http://example.com/fhir/Patient/1",
            },
            {
                "status_code": 200,
                "url": "http://example.com/fhir/Patient/1",
            },
            {
                "status_code": 200,
                "url": "http://example.com/fhir/Observation?subject=1",
            },
        ]


@pytest.mark.asyncio
async def test_graph_definition_with_nested_links_concurrent_requests_401() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: FhirClient = get_graph_processor(max_concurrent_requests=3)

    graph_processor.set_log_all_response_urls(True)

    graph_processor.set_access_token("old_access_token")

    # noinspection PyUnusedLocal
    async def my_refresh_token_function(
        url: Optional[str],
        status_code: Optional[int],
        current_token: Optional[str],
        expiry_date: Optional[datetime],
        retry_count: Optional[int],
    ) -> RefreshTokenResult:
        return RefreshTokenResult(
            access_token="new_access_token", expiry_date=None, abort_request=False
        )

    graph_processor.refresh_token_function(my_refresh_token_function)

    logger: Logger = LoggerForTest()

    graph_json: Dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {
                        "type": "Encounter",
                        "params": "patient={ref}",
                        "link": [
                            {
                                "path": "participant.individual[x]",
                                "target": [{"type": "Practitioner"}],
                            },
                            {
                                "path": "location.location[x]",
                                "target": [{"type": "Location"}],
                            },
                            {
                                "path": "serviceProvider",
                                "target": [{"type": "Organization"}],
                            },
                        ],
                    }
                ]
            },
        ],
    }

    with aioresponses() as m:
        # Mock the HTTP GET request for the initial resource
        m.get(
            "http://example.com/fhir/Patient/1",
            callback=get_payload_function(
                {
                    "resourceType": "OperationOutcome",
                    "issue": [
                        {
                            "severity": "error",
                            "code": "forbidden",
                            "details": {"text": "Unauthorized access"},
                        }
                    ],
                },
                status=401,
                match_access_token="old_access_token",
            ),
        )
        # simulate a transient error
        m.get(
            "http://example.com/fhir/Patient/1",
            callback=get_payload_function(
                {},
                status=502,
                match_access_token="new_access_token",
            ),
        )
        m.get(
            "http://example.com/fhir/Patient/1",
            callback=get_payload_function(
                {"resourceType": "Patient", "id": "1"},
                match_access_token="new_access_token",
            ),
        )
        # Mock the HTTP GET request for the linked Observation
        m.get(
            "http://example.com/fhir/Encounter?patient=1",
            callback=get_payload_function(
                {
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "8",
                                "participant": [
                                    {"individual": {"reference": "Practitioner/12345"}}
                                ],
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "10",
                                "participant": [
                                    {"individual": {"reference": "Practitioner/12345"}}
                                ],
                            }
                        },
                    ]
                },
                match_access_token="new_access_token",
            ),
        )

        m.get(
            "http://example.com/fhir/Practitioner/12345",
            callback=get_payload_function(
                {"resourceType": "Practitioner", "id": "12345"},
                match_access_token="new_access_token",
            ),
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
            max_concurrent_tasks=None,
            sort_resources=True,
        )

        response = [r async for r in async_gen]
        assert len(response) == 1

        m.assert_any_call(url="http://example.com/fhir/Patient/1")
        m.assert_any_call(url="http://example.com/fhir/Encounter?patient=1")
        m.assert_any_call(url="http://example.com/fhir/Practitioner/12345")

        resources: FhirResourceList = response[0].get_resources()
        assert isinstance(resources, FhirResourceList)

        assert (
            len(resources) == 4
        ), f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        encounter = [
            r for r in resources if r["resourceType"] == "Encounter" and r["id"] == "8"
        ][0]
        assert encounter.dict() == {
            "resourceType": "Encounter",
            "id": "8",
            "participant": [{"individual": {"reference": "Practitioner/12345"}}],
        }
        encounter = [
            r for r in resources if r["resourceType"] == "Encounter" and r["id"] == "10"
        ][0]
        assert encounter.dict() == {
            "resourceType": "Encounter",
            "id": "10",
            "participant": [{"individual": {"reference": "Practitioner/12345"}}],
        }
        condition = [r for r in resources if r["resourceType"] == "Practitioner"][0]
        assert condition.dict() == {"resourceType": "Practitioner", "id": "12345"}

        assert response[0].access_token == "new_access_token"
        assert response[0].results_by_url is not None

        assert [
            dict(
                status_code=r.status_code,
                url=r.url,
            )
            for r in response[0].results_by_url
        ] == [
            {
                "status_code": 401,
                "url": "http://example.com/fhir/Patient/1",
            },
            {
                "status_code": 502,
                "url": "http://example.com/fhir/Patient/1",
            },
            {
                "status_code": 200,
                "url": "http://example.com/fhir/Patient/1",
            },
            {
                "status_code": 200,
                "url": "http://example.com/fhir/Encounter?patient=1",
            },
            {
                "status_code": 200,
                "url": "http://example.com/fhir/Practitioner/12345",
            },
        ]
