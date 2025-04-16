from unittest.mock import AsyncMock

import aiohttp
import pytest
from aioresponses import aioresponses

from helix_fhir_client_sdk.exceptions.fhir_sender_exception import FhirSenderException
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.graph.fhir_graph_mixin import FhirGraphMixin
from helix_fhir_client_sdk.graph.graph_definition import GraphDefinition
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


class TestFhirGraphMixin:
    @pytest.fixture
    def fhir_graph_mixin(self) -> FhirGraphMixin:
        """Fixture to create an instance of FhirGraphMixin"""

        class TestClient(FhirClient):
            def __init__(self) -> None:
                super().__init__()
                self.page_size(10)
                self.url("https://fhir-server")
                self.resource("Patient")
                self.log_level("DEBUG")

            def create_http_session(self) -> aiohttp.ClientSession:
                # Mocking the HTTP session creation
                return aiohttp.ClientSession()

        return TestClient()

    @pytest.fixture
    def graph_definition(self) -> GraphDefinition:
        """Fixture to create a mock GraphDefinition"""
        mock_graph_def = AsyncMock(spec=GraphDefinition)
        mock_graph_def.start = "Patient"
        mock_graph_def.to_dict.return_value = {"start": "Patient"}
        return mock_graph_def

    @pytest.mark.asyncio
    async def test_graph_async_single_id(
        self, fhir_graph_mixin: FhirGraphMixin, graph_definition: GraphDefinition
    ) -> None:
        """Test the graph_async method with a single ID"""
        with aioresponses() as m:
            # Mocking the HTTP response
            m.post(
                "https://fhir-server/Patient/123/$graph",
                payload={"resourceType": "Bundle", "type": "searchset"},
            )

            result = [
                response
                async for response in fhir_graph_mixin.graph_async(
                    id_="123",
                    graph_definition=graph_definition,
                    contained=False,
                )
            ]

        assert len(result) > 0
        assert isinstance(result[0], FhirGetResponse)

    @pytest.mark.asyncio
    async def test_graph_async_multiple_ids(
        self, fhir_graph_mixin: FhirGraphMixin, graph_definition: GraphDefinition
    ) -> None:
        """Test the graph_async method with multiple IDs"""
        with aioresponses() as m:
            # Mocking the HTTP response
            m.post(
                "https://fhir-server/Patient/$graph?contained=true&_id=123%252C456",
                payload={"resourceType": "Bundle", "type": "searchset"},
            )
            result = [
                response
                async for response in fhir_graph_mixin.graph_async(
                    id_=["123", "456"],
                    graph_definition=graph_definition,
                    contained=True,
                )
            ]

        assert len(result) > 0
        assert isinstance(result[0], FhirGetResponse)

    @pytest.mark.asyncio
    async def test_graph_async_with_error_handling(
        self, fhir_graph_mixin: FhirGraphMixin, graph_definition: GraphDefinition
    ) -> None:
        """Test the graph_async method with error handling"""
        with aioresponses() as m:
            # Mocking the HTTP response
            m.post(
                "https://fhir-server/Patient/123/$graph",
                status=500,
                payload={"error": "server error"},
            )

            with pytest.raises(FhirSenderException):
                result = [  # noqa: F841
                    response
                    async for response in fhir_graph_mixin.graph_async(
                        id_="123",
                        graph_definition=graph_definition,
                        contained=False,
                    )
                ]

    @pytest.mark.asyncio
    async def test_graph_async_process_in_batches(
        self, fhir_graph_mixin: FhirGraphMixin, graph_definition: GraphDefinition
    ) -> None:
        """Test the graph_async method with batch processing enabled"""
        with aioresponses() as m:
            # Mocking the HTTP response
            m.post(
                "https://fhir-server/Patient/$graph?_id=123%252C456%252C789",
                payload={"resourceType": "Bundle", "type": "searchset"},
            )

            result = [
                response
                async for response in fhir_graph_mixin.graph_async(
                    id_=["123", "456", "789"],
                    graph_definition=graph_definition,
                    contained=False,
                )
            ]

        assert len(result) > 0
        assert isinstance(result[0], FhirGetResponse)

    @pytest.mark.asyncio
    async def test_graph(self, fhir_graph_mixin: FhirGraphMixin, graph_definition: GraphDefinition) -> None:
        """Test the graph method"""
        with aioresponses() as m:
            # Mocking the HTTP response for AsyncRunner.run
            m.post(
                "https://fhir-server/Patient/1/$graph",
                payload={"resourceType": "Bundle", "type": "searchset"},
            )

            response = fhir_graph_mixin.graph(
                graph_definition=graph_definition,
                contained=False,
            )

        assert isinstance(response, FhirGetResponse)
