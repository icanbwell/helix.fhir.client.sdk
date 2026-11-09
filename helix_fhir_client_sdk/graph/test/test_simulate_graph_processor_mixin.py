import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from logging import Logger
from typing import Any, cast

import aiohttp
import pytest
from aioresponses import CallbackResult, aioresponses
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from yarl import URL

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.function_types import RefreshTokenResult
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
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

    def create_http_session(self, connection_limit: int = 100) -> aiohttp.ClientSession:
        """
        Create a mock HTTP session.
        """
        return aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=connection_limit))


def get_graph_processor(*, max_concurrent_requests: int | None = None) -> FhirClient:
    """
    Fixture to create an instance of the SimulatedGraphProcessorMixin class.
    """
    processor: FhirClient = TestGraphProcessor()
    processor = cast(FhirClient, processor.set_max_concurrent_requests(max_concurrent_requests))
    return processor


def get_payload_function(
    payload: dict[str, Any],
    delay: int = 0,
    status: int = 200,
    match_access_token: str | None = None,
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
            access_token = kwargs.get("headers", {}).get("Authorization", "").replace("Bearer ", "")
            if access_token != match_access_token:
                await asyncio.sleep(delay)  # 2 second delay
                return CallbackResult(
                    status=401,
                    headers={},
                    body=json.dumps({"error": f"Unauthorized: Unexpected access token: {access_token}"}),
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

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    graph_json: dict[str, Any] = {
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

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    graph_json: dict[str, Any] = {
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

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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

    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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

        assert len(resources) == 3, f"Expected 3 resources, got {len(resources)}: {resources}"
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
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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
        assert len(resources) == 3, f"Expected 3 resources, got {len(resources)}: {resources}"
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
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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

        assert len(resources) == 3, f"Expected 3 resources, got {len(resources)}: {resources}"
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
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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
        m.get("http://example.com/fhir/Patient?_id=1,2,3", payload=payload)

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

        patient = [r for r in resources if r["resourceType"] == "Patient" and r["id"] == "1"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        patient = [r for r in resources if r["resourceType"] == "Patient" and r["id"] == "2"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "2"}
        patient = [r for r in resources if r["resourceType"] == "Patient" and r["id"] == "3"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "3"}


@pytest.mark.asyncio
async def test_process_target_async_batches_fetch_concurrently() -> None:
    """
    Regression guard (DCON-5261): _process_target_async() used to await each
    request_size-bounded batch's fetch before assembling the next, so N
    independent batches for one target took N sequential round trips. With
    three patients and request_size defaulting to 1, the Encounter link
    below produces three separate batches (Encounter?patient=1/2/3).

    Asserts directly on how many of those three fetches were ever
    in-flight at once (tracked by the delayed callback below), rather than
    on wall-clock time — a fixed elapsed-time threshold is flaky across
    cold/warm test runs (e.g. first-request connection/SSL context setup
    overhead can dwarf the delay itself), whereas "were N requests
    in-flight simultaneously" is unaffected by that overhead and can only
    be true if the batches were actually fetched concurrently.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=3)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [{"target": [{"type": "Encounter", "params": "patient={ref}"}]}],
    }

    in_flight = 0
    max_in_flight = 0

    def make_delayed_encounter_callback(patient_id: str) -> Callable[..., Awaitable[CallbackResult]]:
        async def _callback(url: str, **kwargs: Any) -> CallbackResult:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.1)
            in_flight -= 1
            return CallbackResult(
                status=200,
                headers={},
                body=json.dumps({"entry": [{"resource": {"resourceType": "Encounter", "id": f"e{patient_id}"}}]}),
            )

        return _callback

    with aioresponses() as m:
        payload = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "1"}},
                {"resource": {"resourceType": "Patient", "id": "2"}},
                {"resource": {"resourceType": "Patient", "id": "3"}},
            ],
        }
        m.get("http://example.com/fhir/Patient?_id=1,2,3", payload=payload)

        for patient_id in ["1", "2", "3"]:
            m.get(
                f"http://example.com/fhir/Encounter?patient={patient_id}",
                callback=make_delayed_encounter_callback(patient_id),
            )

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
            max_concurrent_tasks=3,
            sort_resources=True,
        )
        response = [r async for r in async_gen]

    assert len(response) == 1
    resources: FhirResourceList = response[0].get_resources()
    encounter_ids = sorted(r["id"] for r in resources if r["resourceType"] == "Encounter")
    assert encounter_ids == ["e1", "e2", "e3"]

    # All three batches must have been in flight at the same time at some
    # point — sequential fetching (the pre-fix behavior) would never let
    # in_flight exceed 1.
    assert max_in_flight == 3, f"expected all 3 batches in flight concurrently, saw max {max_in_flight}"


@pytest.mark.asyncio
async def test_get_resources_by_id_one_by_one_fetches_concurrently() -> None:
    """
    Regression guard (DCON-5261): _get_resources_by_id_one_by_one_async() —
    the fallback used once a resource type is found not to support batch
    ?_id=a,b search — used to fetch each id with a plain sequential
    for/await loop. Forcing that fallback here (the combined ?_id=1,2,3
    search below returns 400) for three patient ids and asserting on how
    many were ever in flight at once (see the identical technique in
    test_process_target_async_batches_fetch_concurrently for why this is
    used instead of a wall-clock threshold) proves they now fetch
    concurrently instead of one at a time.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=3)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [],
    }

    in_flight = 0
    max_in_flight = 0

    def make_delayed_patient_callback(patient_id: str) -> Callable[..., Awaitable[CallbackResult]]:
        async def _callback(url: str, **kwargs: Any) -> CallbackResult:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.1)
            in_flight -= 1
            return CallbackResult(
                status=200,
                headers={},
                body=json.dumps({"resourceType": "Patient", "id": patient_id}),
            )

        return _callback

    with aioresponses() as m:
        # Force the one-by-one fallback: the combined _id search fails.
        m.get(
            "http://example.com/fhir/Patient?_id=1,2,3",
            status=400,
            payload={"resourceType": "OperationOutcome"},
        )
        for patient_id in ["1", "2", "3"]:
            m.get(
                f"http://example.com/fhir/Patient/{patient_id}",
                callback=make_delayed_patient_callback(patient_id),
            )

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
            max_concurrent_tasks=3,
            sort_resources=True,
        )
        response = [r async for r in async_gen]

    assert len(response) == 1
    resources: FhirResourceList = response[0].get_resources()
    patient_ids = sorted(r["id"] for r in resources if r["resourceType"] == "Patient")
    assert patient_ids == ["1", "2", "3"]

    # All three one-by-one fetches must have been in flight at the same
    # time at some point — the pre-fix sequential loop would never let
    # in_flight exceed 1.
    assert max_in_flight == 3, f"expected all 3 one-by-one fetches in flight concurrently, saw max {max_in_flight}"


@pytest.mark.asyncio
async def test_get_resources_by_id_one_by_one_respects_max_concurrent_tasks_bound() -> None:
    """
    Integration-level check that concurrent HTTP request count never exceeds
    max_concurrent_tasks, with request count (6) exceeding max_concurrent_tasks (2)
    so an implementation with no concurrency bound at all would let all 6 run at once.

    NOTE: this does NOT regression-test the DCON-5378 fix itself. Both the old
    semaphore-gated-but-eager-Task-creation implementation and the new bounded
    worker pool correctly bound concurrent *request* execution here - the bug
    DCON-5378 fixes (creating one asyncio.Task per row up front regardless of
    max_concurrent_tasks) is a Task-object memory cost, not a concurrency-bound
    bug, so it isn't observable via in-flight request counting. The actual
    regression guard for that bug is the lower-level
    test_process_rows_in_parallel_does_not_create_all_tasks_up_front in
    test_async_parallel_processor.py, which asserts on Task creation count
    directly. This test is still valuable as an independent confirmation that
    max_concurrent_tasks bounds real request concurrency through the full
    SimulatedGraphProcessorMixin path, complementing
    test_get_resources_by_id_one_by_one_fetches_concurrently above (which only
    proves concurrency exists at all, with request count == max_concurrent_tasks
    so it can't distinguish bounded from unbounded).
    """
    max_concurrent_tasks = 2
    patient_ids = [str(i) for i in range(1, 7)]
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=len(patient_ids))

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [],
    }

    in_flight = 0
    max_in_flight = 0

    def make_delayed_patient_callback(patient_id: str) -> Callable[..., Awaitable[CallbackResult]]:
        async def _callback(url: str, **kwargs: Any) -> CallbackResult:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.1)
            in_flight -= 1
            return CallbackResult(
                status=200,
                headers={},
                body=json.dumps({"resourceType": "Patient", "id": patient_id}),
            )

        return _callback

    with aioresponses() as m:
        # Force the one-by-one fallback: the combined _id search fails.
        m.get(
            f"http://example.com/fhir/Patient?_id={','.join(patient_ids)}",
            status=400,
            payload={"resourceType": "OperationOutcome"},
        )
        for patient_id in patient_ids:
            m.get(
                f"http://example.com/fhir/Patient/{patient_id}",
                callback=make_delayed_patient_callback(patient_id),
            )

        async_gen = graph_processor.process_simulate_graph_async(
            id_=patient_ids,
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
            max_concurrent_tasks=max_concurrent_tasks,
            sort_resources=True,
        )
        response = [r async for r in async_gen]

    assert len(response) == 1
    resources: FhirResourceList = response[0].get_resources()
    fetched_ids = sorted(r["id"] for r in resources if r["resourceType"] == "Patient")
    assert fetched_ids == patient_ids

    assert max_in_flight == max_concurrent_tasks, (
        f"expected at most {max_concurrent_tasks} one-by-one fetches in flight at once, saw max {max_in_flight}"
    )


@pytest.mark.asyncio
async def test_graph_definition_with_multiple_links_concurrent_requests() -> None:
    """
    Test GraphDefinition with multiple targets.
    """
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=3)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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

        assert len(resources) == 3, f"Expected 3 resources, got {len(resources)}: {resources}"
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
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=3)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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

        assert len(resources) == 3, f"Expected 3 resources, got {len(resources)}: {resources}"
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
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=3)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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
                                "participant": [{"individual": {"reference": "Practitioner/12345"}}],
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "10",
                                "participant": [{"individual": {"reference": "Practitioner/12345"}}],
                            }
                        },
                    ]
                }
            ),
        )

        m.get(
            "http://example.com/fhir/Practitioner/12345",
            callback=get_payload_function({"resourceType": "Practitioner", "id": "12345"}),
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

        assert len(resources) == 4, f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        encounter = [r for r in resources if r["resourceType"] == "Encounter" and r["id"] == "8"][0]
        assert encounter.dict() == {
            "resourceType": "Encounter",
            "id": "8",
            "participant": [{"individual": {"reference": "Practitioner/12345"}}],
        }
        encounter = [r for r in resources if r["resourceType"] == "Encounter" and r["id"] == "10"][0]
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
        url: str | None,
        status_code: int | None,
        current_token: str | None,
        expiry_date: datetime | None,
        retry_count: int | None,
    ) -> RefreshTokenResult:
        return RefreshTokenResult(access_token="new_access_token", expiry_date=None, abort_request=False)

    graph_processor.refresh_token_function(my_refresh_token_function)

    graph_json: dict[str, Any] = {
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
        url: str | None,
        status_code: int | None,
        current_token: str | None,
        expiry_date: datetime | None,
        retry_count: int | None,
    ) -> RefreshTokenResult:
        return RefreshTokenResult(access_token="new_access_token", expiry_date=None, abort_request=False)

    graph_processor.refresh_token_function(my_refresh_token_function)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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
        url: str | None,
        status_code: int | None,
        current_token: str | None,
        expiry_date: datetime | None,
        retry_count: int | None,
    ) -> RefreshTokenResult:
        return RefreshTokenResult(access_token="new_access_token", expiry_date=None, abort_request=False)

    graph_processor.refresh_token_function(my_refresh_token_function)

    logger: Logger = LoggerForTest()

    graph_json: dict[str, Any] = {
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
                                "participant": [{"individual": {"reference": "Practitioner/12345"}}],
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Encounter",
                                "id": "10",
                                "participant": [{"individual": {"reference": "Practitioner/12345"}}],
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

        assert len(resources) == 4, f"Expected 3 resources, got {len(resources)}: {resources}"
        patient = [r for r in resources if r["resourceType"] == "Patient"][0]
        assert patient.dict() == {"resourceType": "Patient", "id": "1"}
        encounter = [r for r in resources if r["resourceType"] == "Encounter" and r["id"] == "8"][0]
        assert encounter.dict() == {
            "resourceType": "Encounter",
            "id": "8",
            "participant": [{"individual": {"reference": "Practitioner/12345"}}],
        }
        encounter = [r for r in resources if r["resourceType"] == "Encounter" and r["id"] == "10"][0]
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


def _long_ids(prefix: str, count: int, width: int = 40) -> list[str]:
    """Distinct ids of exactly ``width`` characters, like Epic's long Medication ids."""
    return [f"{prefix}{i}".ljust(width, "x") for i in range(count)]


def _requested_id_batches(requests: dict[Any, Any], *, resource_type: str, query_key: str) -> list[list[str]]:
    """The ``query_key=a,b,c`` id lists sent to ``resource_type``, in a stable order."""
    batches: list[list[str]] = []
    for _, url in requests:
        if url.path.endswith(f"/{resource_type}") and query_key in url.query:
            batches.append(url.query[query_key].split(","))
        elif f"/{resource_type}/" in url.path:
            # a batch of one id is read as ``{resource_type}/{id}``
            batches.append([url.path.rsplit("/", 1)[-1]])
    return sorted(batches)


async def _run_batching_graph(
    *,
    graph_json: dict[str, Any],
    parent_resources: list[dict[str, Any]],
    child_resource_type: str,
    child_query_key: str,
    request_size: int,
    max_query_chars: int | None,
) -> tuple[list[list[str]], FhirResourceList]:
    """Run ``graph_json`` for Patient/1 -> ``parent_resources`` and record the child batches sent."""
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor()

    def _children_callback(url: Any, **kwargs: Any) -> CallbackResult:
        ids = URL(str(url)).query.get(child_query_key, "").split(",")
        return CallbackResult(
            status=200,
            headers={},
            body=json.dumps(
                {
                    "resourceType": "Bundle",
                    "entry": [
                        {"resource": {"resourceType": child_resource_type, "id": i}}
                        for i in ids
                        if i and child_resource_type == "Medication"
                    ],
                }
            ),
        )

    def _single_read_callback(url: Any, **kwargs: Any) -> CallbackResult:
        return CallbackResult(
            status=200,
            headers={},
            body=json.dumps({"resourceType": child_resource_type, "id": URL(str(url)).path.rsplit("/", 1)[-1]}),
        )

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Patient", "id": "1"},
        )
        m.get(
            f"http://example.com/fhir/{parent_resources[0]['resourceType']}?patient=1",
            payload={"resourceType": "Bundle", "entry": [{"resource": r} for r in parent_resources]},
        )
        m.get(
            re.compile(rf"^http://example\.com/fhir/{child_resource_type}\?.*"),
            callback=_children_callback,
            repeat=True,
        )
        m.get(
            re.compile(rf"^http://example\.com/fhir/{child_resource_type}/[^?]+$"),
            callback=_single_read_callback,
            repeat=True,
        )
        responses = [
            r
            async for r in graph_processor.process_simulate_graph_async(
                id_=["1"],
                graph_json=graph_json,
                contained=False,
                separate_bundle_resources=False,
                restrict_to_scope=None,
                restrict_to_resources=None,
                restrict_to_capability_statement=None,
                retrieve_and_restrict_to_capability_statement=None,
                ifModifiedSince=None,
                eTag=None,
                logger=LoggerForTest(),
                url=None,
                expand_fhir_bundle=False,
                auth_scopes=[],
                request_size=request_size,
                max_query_chars=max_query_chars,
                max_concurrent_tasks=None,
                sort_resources=True,
            )
        ]
        batches = _requested_id_batches(m.requests, resource_type=child_resource_type, query_key=child_query_key)
    assert len(responses) == 1
    return batches, responses[0].get_resources()


# Five 40-character ids: 41 characters each once the comma is counted.
_BATCHING_CASES = [
    pytest.param(25, None, [[0, 1, 2, 3, 4]], id="no-budget-fills-to-request-size"),
    pytest.param(25, 100, [[0, 1], [2, 3], [4]], id="budget-splits-before-an-id-would-overflow"),
    pytest.param(2, 1000, [[0, 1], [2, 3], [4]], id="request-size-still-applies"),
    pytest.param(25, 10, [[0], [1], [2], [3], [4]], id="id-longer-than-budget-goes-alone"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("request_size", "max_query_chars", "expected"), _BATCHING_CASES)
async def test_max_query_chars_splits_single_reference_batches(
    request_size: int, max_query_chars: int | None, expected: list[list[int]]
) -> None:
    """A referenced-read batch (``medicationReference`` -> ``Medication?_id=a,b,c``) stops
    growing before its id list would pass ``max_query_chars``, so an id-heavy type no longer
    produces one oversized query that the server rejects."""
    ids = _long_ids("med", 5)
    graph_json: dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {
                        "type": "MedicationRequest",
                        "params": "patient={ref}",
                        "link": [{"path": "medicationReference", "target": [{"type": "Medication"}]}],
                    }
                ]
            }
        ],
    }
    requests = [
        {"resourceType": "MedicationRequest", "id": f"mr{i}", "medicationReference": {"reference": f"Medication/{m}"}}
        for i, m in enumerate(ids)
    ]

    batches, resources = await _run_batching_graph(
        graph_json=graph_json,
        parent_resources=requests,
        child_resource_type="Medication",
        child_query_key="_id",
        request_size=request_size,
        max_query_chars=max_query_chars,
    )

    assert batches == sorted([ids[i] for i in batch] for batch in expected)
    assert sorted(r["id"] for r in resources if r["resourceType"] == "Medication") == ids


@pytest.mark.asyncio
@pytest.mark.parametrize(("request_size", "max_query_chars", "expected"), _BATCHING_CASES)
async def test_max_query_chars_splits_array_reference_batches(
    request_size: int, max_query_chars: int | None, expected: list[list[int]]
) -> None:
    """Same budget for a ``[x]`` path: ``MedicationRequest.reasonReference[x]`` style lists."""
    ids = _long_ids("med", 5)
    graph_json: dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {
                        "type": "MedicationRequest",
                        "params": "patient={ref}",
                        "link": [{"path": "supportingInformation[x]", "target": [{"type": "Medication"}]}],
                    }
                ]
            }
        ],
    }
    requests = [
        {
            "resourceType": "MedicationRequest",
            "id": f"mr{i}",
            "supportingInformation": [{"reference": f"Medication/{m}"}],
        }
        for i, m in enumerate(ids)
    ]

    batches, resources = await _run_batching_graph(
        graph_json=graph_json,
        parent_resources=requests,
        child_resource_type="Medication",
        child_query_key="_id",
        request_size=request_size,
        max_query_chars=max_query_chars,
    )

    assert batches == sorted([ids[i] for i in batch] for batch in expected)
    assert sorted(r["id"] for r in resources if r["resourceType"] == "Medication") == ids


@pytest.mark.asyncio
@pytest.mark.parametrize(("request_size", "max_query_chars", "expected"), _BATCHING_CASES)
async def test_max_query_chars_splits_reverse_link_batches(
    request_size: int, max_query_chars: int | None, expected: list[list[int]]
) -> None:
    """Same budget for a reverse link: ``MedicationDispense?prescription=a,b,c`` over parent ids."""
    parent_ids = _long_ids("mr", 5)
    graph_json: dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [
            {
                "target": [
                    {
                        "type": "MedicationRequest",
                        "params": "patient={ref}",
                        "link": [
                            {"target": [{"type": "MedicationDispense", "params": "prescription={ref}"}]},
                        ],
                    }
                ]
            }
        ],
    }
    requests = [{"resourceType": "MedicationRequest", "id": i} for i in parent_ids]

    batches, _ = await _run_batching_graph(
        graph_json=graph_json,
        parent_resources=requests,
        child_resource_type="MedicationDispense",
        child_query_key="prescription",
        request_size=request_size,
        max_query_chars=max_query_chars,
    )

    assert batches == sorted([parent_ids[i] for i in batch] for batch in expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("max_query_chars", [0, -1, -500, True, 2.5])
async def test_max_query_chars_must_be_none_or_a_positive_int(max_query_chars: Any) -> None:
    """0 would silently turn the cap off and a negative value would send every id alone,
    so a bad value is rejected up front instead of changing the request count."""
    graph_json: dict[str, Any] = {
        "id": "1",
        "name": "Test Graph",
        "resourceType": "GraphDefinition",
        "start": "Patient",
        "link": [{"target": [{"type": "MedicationRequest", "params": "patient={ref}"}]}],
    }

    with pytest.raises(ValueError, match="max_query_chars"):
        await _run_batching_graph(
            graph_json=graph_json,
            parent_resources=[{"resourceType": "MedicationRequest", "id": "mr1"}],
            child_resource_type="Medication",
            child_query_key="_id",
            request_size=25,
            max_query_chars=max_query_chars,
        )
