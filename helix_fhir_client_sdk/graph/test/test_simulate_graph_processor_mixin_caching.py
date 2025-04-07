from typing import List, Optional, Tuple, Union, AsyncGenerator, cast, Any
from unittest.mock import Mock

# noinspection PyPackageRequirements
import pytest

from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource

# Import the actual SimulatedGraphProcessorMixin (replace with actual import path)
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.loggers.fhir_logger import FhirLogger
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser

# Necessary imports from the SDK
from helix_fhir_client_sdk.utilities.request_cache import RequestCache


class MockSimulatedGraphProcessorMixin:
    def __init__(self) -> None:
        # Mock necessary attributes
        self._access_token: str = "test-token"
        self._storage_mode: str = "memory"
        self._create_operation_outcome_for_error: bool = False
        self._url: str = "https://test.example.com"
        self._expand_fhir_bundle: bool = False
        self._logger: Optional[FhirLogger] = None
        self._auth_scopes: List[str] = ["test-scope"]
        self._additional_parameters: Optional[List[str]] = None
        self._log_level: str = "INFO"

    async def _get_with_session_async(
        self, **kwargs: Any
    ) -> AsyncGenerator[FhirGetResponse, None]:
        # Create a mock resource based on input
        resource_id: str = kwargs.get("ids", ["test-id"])[0]
        resource_type: str = kwargs.get("resource_type", "Patient")

        mock_resource: FhirResource = FhirResource(
            {"id": resource_id, "resourceType": resource_type}
        )
        mock_bundle_entry: FhirBundleEntry = FhirBundleEntry(resource=mock_resource)

        # Create a mock response
        mock_response: FhirGetResponse = Mock(spec=FhirGetResponse)
        mock_response.status = 200
        mock_response.get_bundle_entries.return_value = [mock_bundle_entry]  # type: ignore[attr-defined]
        mock_response.get_resource_count.return_value = 1  # type: ignore[attr-defined]
        mock_response.resource_type = resource_type
        mock_response.url = self._url

        yield mock_response

    # noinspection PyMethodMayBeStatic
    async def _get_resources_by_id_one_by_one_async(
        self, **kwargs: Any
    ) -> Optional[FhirGetResponse]:
        # Mock implementation for fallback ID retrieval
        resource_type: str = cast(str, kwargs.get("resource_type"))
        ids: List[str] = kwargs.get("ids", [])

        mock_responses: List[FhirGetResponse] = []
        for resource_id in ids:
            mock_resource: FhirResource = FhirResource(
                {"id": resource_id, "resourceType": resource_type}
            )
            mock_bundle_entry: FhirBundleEntry = FhirBundleEntry(resource=mock_resource)

            mock_response: FhirGetResponse = Mock(spec=FhirGetResponse)
            mock_response.status = 200
            mock_response.get_bundle_entries.return_value = [mock_bundle_entry]  # type: ignore[attr-defined]
            mock_response.get_resource_count.return_value = 1  # type: ignore[attr-defined]
            mock_response.resource_type = resource_type

            mock_responses.append(mock_response)

        # Combine responses if multiple
        if len(mock_responses) > 1:
            combined_response: FhirGetResponse = mock_responses[0]
            for resp in mock_responses[1:]:
                # noinspection PyUnresolvedReferences
                combined_response.get_bundle_entries.return_value.extend(  # type: ignore[attr-defined]
                    resp.get_bundle_entries.return_value  # type: ignore[attr-defined]
                )
                # noinspection PyUnresolvedReferences
                combined_response.get_resource_count.return_value += (  # type: ignore[attr-defined]
                    resp.get_resource_count.return_value  # type: ignore[attr-defined]
                )
            return combined_response

        return mock_responses[0] if mock_responses else None

    def separate_bundle_resources(self, value: bool) -> None:
        # Mock method for bundle resource separation
        pass

    def additional_parameters(self, params: Optional[List[str]]) -> None:
        # Mock method for additional parameters
        self._additional_parameters = params or []

    async def _get_resources_by_parameters_async(
        self,
        id_: Optional[Union[List[str], str]],
        resource_type: str,
        parameters: Optional[List[str]] = None,
        cache: Optional[RequestCache] = None,
        scope_parser: Optional[FhirScopeParser] = None,
        logger: Optional[FhirLogger] = None,
        id_search_unsupported_resources: Optional[List[str]] = None,
    ) -> Tuple[FhirGetResponse, int]:
        # noinspection PyProtectedMember
        return await SimulatedGraphProcessorMixin._get_resources_by_parameters_async(
            self=cast(SimulatedGraphProcessorMixin, self),
            id_=id_,
            resource_type=resource_type,
            parameters=parameters,
            cache=cache or RequestCache(),
            scope_parser=scope_parser or Mock(spec=FhirScopeParser),
            logger=logger,
            id_search_unsupported_resources=id_search_unsupported_resources or [],
        )


@pytest.mark.ignore("not working yet")
class TestGetResourcesByParametersAsync:
    @pytest.fixture
    def mock_processor(self) -> MockSimulatedGraphProcessorMixin:
        # Create a mock processor with the method we're testing
        return MockSimulatedGraphProcessorMixin()

    @pytest.fixture
    def mock_scope_parser(self) -> FhirScopeParser:
        """Create a mock scope parser that always allows resources."""
        mock_parser: FhirScopeParser = Mock(spec=FhirScopeParser)
        mock_parser.scope_allows.return_value = True  # type: ignore[attr-defined]
        return mock_parser

    @pytest.mark.asyncio
    async def test_cache_hit_single_resource(
        self,
        mock_processor: MockSimulatedGraphProcessorMixin,
        mock_scope_parser: FhirScopeParser,
    ) -> None:
        """Test scenario where all requested resources are in cache."""
        cache: RequestCache = RequestCache()

        # Simulate a cached resource
        mock_resource: FhirResource = FhirResource(
            {"id": "cached-id", "resourceType": "Patient"}
        )
        mock_bundle_entry: FhirBundleEntry = FhirBundleEntry(resource=mock_resource)
        cache.add(
            resource_type="Patient",
            resource_id="cached-id",
            bundle_entry=mock_bundle_entry,
        )

        result, cache_hits = await mock_processor._get_resources_by_parameters_async(
            id_="cached-id",
            resource_type="Patient",
            parameters=None,
            cache=cache,
            scope_parser=mock_scope_parser,
            logger=None,
            id_search_unsupported_resources=[],
        )

        assert cache_hits == 1
        assert len(result.get_bundle_entries()) == 1
        resource = result.get_bundle_entries()[0].resource
        assert resource
        assert resource.get("id") == "cached-id"

    @pytest.mark.asyncio
    async def test_mixed_cache_and_fetch(
        self,
        mock_processor: MockSimulatedGraphProcessorMixin,
        mock_scope_parser: FhirScopeParser,
    ) -> None:
        """Test scenario with some cached and some non-cached resources."""
        cache: RequestCache = RequestCache()

        # Simulate a cached resource
        mock_cached_resource: FhirResource = FhirResource(
            {"id": "cached-id", "resourceType": "Patient"}
        )
        mock_cached_bundle_entry: FhirBundleEntry = FhirBundleEntry(
            resource=mock_cached_resource
        )
        cache.add(
            resource_type="Patient",
            resource_id="cached-id",
            bundle_entry=mock_cached_bundle_entry,
        )

        result, cache_hits = await mock_processor._get_resources_by_parameters_async(
            id_=["cached-id", "non-cached-id"],
            resource_type="Patient",
            parameters=None,
            cache=cache,
            scope_parser=mock_scope_parser,
            logger=None,
            id_search_unsupported_resources=[],
        )

        assert cache_hits == 1
        assert len(result.get_bundle_entries()) == 2  # Cached + fetched resource

    @pytest.mark.asyncio
    async def test_no_cache_hit(
        self,
        mock_processor: MockSimulatedGraphProcessorMixin,
        mock_scope_parser: FhirScopeParser,
    ) -> None:
        """Test scenario where no resources are in cache."""
        cache: RequestCache = RequestCache()

        result, cache_hits = await mock_processor._get_resources_by_parameters_async(
            id_="non-cached-id",
            resource_type="Patient",
            parameters=None,
            cache=cache,
            scope_parser=mock_scope_parser,
            logger=None,
            id_search_unsupported_resources=[],
        )

        assert cache_hits == 0
        assert len(result.get_bundle_entries()) == 1

    @pytest.mark.asyncio
    async def test_scope_restriction(
        self, mock_processor: MockSimulatedGraphProcessorMixin
    ) -> None:
        """Test scenario where resource is not allowed by scope."""
        mock_scope_parser: FhirScopeParser = Mock(spec=FhirScopeParser)
        mock_scope_parser.scope_allows.return_value = False  # type: ignore[attr-defined]

        cache: RequestCache = RequestCache()

        result, cache_hits = await mock_processor._get_resources_by_parameters_async(
            id_="test-id",
            resource_type="Patient",
            parameters=None,
            cache=cache,
            scope_parser=mock_scope_parser,
            logger=None,
            id_search_unsupported_resources=[],
        )

        assert cache_hits == 0
        assert result.total_count == 0
        # noinspection PyUnresolvedReferences
        mock_scope_parser.scope_allows.assert_called_once_with(resource_type="Patient")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_empty_id_list(
        self,
        mock_processor: MockSimulatedGraphProcessorMixin,
        mock_scope_parser: FhirScopeParser,
    ) -> None:
        """Test scenario with an empty ID list."""
        cache: RequestCache = RequestCache()

        result, cache_hits = await mock_processor._get_resources_by_parameters_async(
            id_=None,
            resource_type="Patient",
            parameters=None,
            cache=cache,
            scope_parser=mock_scope_parser,
            logger=None,
            id_search_unsupported_resources=[],
        )

        assert cache_hits == 0
        assert len(result.get_bundle_entries()) == 1

    @pytest.mark.asyncio
    async def test_caching_fetched_resources(
        self,
        mock_processor: MockSimulatedGraphProcessorMixin,
        mock_scope_parser: FhirScopeParser,
    ) -> None:
        """Test that fetched resources are added to the cache."""
        cache: RequestCache = RequestCache()

        result, _ = await mock_processor._get_resources_by_parameters_async(
            id_="test-id",
            resource_type="Patient",
            parameters=None,
            cache=cache,
            scope_parser=mock_scope_parser,
            logger=None,
            id_search_unsupported_resources=[],
        )

        # Check that the fetched resource was added to the cache
        cached_entry: Optional[FhirBundleEntry] = cache.get(
            resource_type="Patient", resource_id="test-id"
        )
        assert cached_entry is not None
        resource = cached_entry.resource
        assert resource is not None
        assert resource.get("id") == "test-id"
