import json
from typing import Optional, List, AsyncGenerator
from unittest.mock import MagicMock

import pytest
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.function_types import HandleStreamingChunkFunction
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_single_response import (
    FhirGetSingleResponse,
)
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache


class MockSimulatedGraphProcessor(SimulatedGraphProcessorMixin):
    """Mock implementation of SimulatedGraphProcessorMixin for testing."""

    def __init__(self) -> None:
        self._access_token = None
        self._storage_mode: CompressedDictStorageMode = CompressedDictStorageMode.raw()
        self._create_operation_outcome_for_error = None
        self._logger = None
        self._url = None
        self._expand_fhir_bundle = False
        self._auth_scopes = None
        self._additional_parameters = None


@pytest.mark.asyncio
async def test_cache_hit() -> None:
    """Test that resources are retrieved from the cache when available."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()
    mock_entry = FhirBundleEntry(
        resource=FhirResource({"id": "test-id", "resourceType": "Patient"})
    )
    await cache.add_async(
        resource_type="Patient",
        resource_id="test-id",
        bundle_entry=mock_entry,
        status=200,
        last_modified=None,
        etag=None,
    )

    result, cache_hits = await processor._get_resources_by_parameters_async(
        id_="test-id",
        resource_type="Patient",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    assert cache_hits == 1
    assert len(result.get_bundle_entries()) == 1
    resource = result.get_bundle_entries()[0].resource
    assert resource is not None
    assert resource.get("id") == "test-id"


@pytest.mark.asyncio
async def test_cache_miss() -> None:
    """Test that resources are fetched from the server when not in the cache."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        resource_type: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps({"id": "test-id-1", "resourceType": "Patient"}),
            status=200,
            total_count=1,
            next_url=None,
            resource_type="Patient",
            id_="test-id-1",
            response_headers=None,
            chunk_number=0,
            cache_hits=0,
            results_by_url=[],
            storage_mode=CompressedDictStorageMode.raw(),
            error=None,
            access_token=None,
            extra_context_to_return=None,
            request_id=None,
            url="http://example.com/fhir/Patient/test-id-1",
        )
        yield FhirGetSingleResponse(
            response_text=json.dumps({"id": "test-id-2", "resourceType": "Patient"}),
            status=200,
            total_count=1,
            next_url=None,
            resource_type="Patient",
            id_="test-id-2",
            response_headers=None,
            chunk_number=1,
            cache_hits=0,
            results_by_url=[],
            storage_mode=CompressedDictStorageMode.raw(),
            error=None,
            access_token=None,
            extra_context_to_return=None,
            request_id=None,
            url="http://example.com/fhir/Patient/test-id-2",
        )

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    result, cache_hits = await processor._get_resources_by_parameters_async(
        id_="test-id",
        resource_type="Patient",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    assert cache_hits == 0
    assert len(result.get_bundle_entries()) == 2
    resource = result.get_bundle_entries()[0].resource
    assert resource is not None
    assert resource.get("id") == "test-id-1"
    resource = result.get_bundle_entries()[1].resource
    assert resource is not None
    assert resource.get("id") == "test-id-2"


@pytest.mark.asyncio
async def test_partial_cache() -> None:
    """Test a scenario where some resources are in the cache and others are fetched."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()
    mock_entry = FhirBundleEntry(
        resource=FhirResource({"id": "cached-id", "resourceType": "Patient"})
    )
    await cache.add_async(
        resource_type="Patient",
        resource_id="cached-id",
        bundle_entry=mock_entry,
        status=200,
        last_modified=None,
        etag=None,
    )

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        resource_type: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps(
                {"id": "non-cached-id", "resourceType": "Patient"}
            ),
            status=200,
            total_count=1,
            next_url=None,
            resource_type="Patient",
            id_="non-cached-id",
            response_headers=None,
            chunk_number=0,
            cache_hits=0,
            results_by_url=[],
            storage_mode=CompressedDictStorageMode.raw(),
            error=None,
            access_token=None,
            extra_context_to_return=None,
            request_id=None,
            url="http://example.com/fhir/Patient/non-cached-id",
        )

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    result, cache_hits = await processor._get_resources_by_parameters_async(
        id_=["cached-id", "non-cached-id"],
        resource_type="Patient",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    assert cache_hits == 1
    assert len(result.get_bundle_entries()) == 2
    resource_ids = [
        entry.resource.get("id")
        for entry in result.get_bundle_entries()
        if entry.resource
    ]
    assert set(resource_ids) == {"cached-id", "non-cached-id"}


@pytest.mark.asyncio
async def test_partial_cache_with_null_bundle_entry() -> None:
    """Test a scenario where some resources are in the cache and others are fetched."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    await cache.add_async(
        resource_type="Patient",
        resource_id="cached-id",
        bundle_entry=None,
        status=200,
        last_modified=None,
        etag=None,
    )

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        resource_type: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps(
                {"id": "non-cached-id", "resourceType": "Patient"}
            ),
            status=200,
            total_count=1,
            next_url=None,
            resource_type="Patient",
            id_="non-cached-id",
            response_headers=None,
            chunk_number=0,
            cache_hits=0,
            results_by_url=[],
            storage_mode=CompressedDictStorageMode.raw(),
            error=None,
            access_token=None,
            extra_context_to_return=None,
            request_id=None,
            url="http://example.com/fhir/Patient/non-cached-id",
        )

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    result, cache_hits = await processor._get_resources_by_parameters_async(
        id_=["cached-id", "non-cached-id"],
        resource_type="Patient",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    assert cache_hits == 1
    assert len(result.get_bundle_entries()) == 1
    resource_ids = [
        entry.resource.get("id")
        for entry in result.get_bundle_entries()
        if entry.resource
    ]
    assert set(resource_ids) == {"non-cached-id"}


@pytest.mark.asyncio
async def test_cache_update() -> None:
    """Test that fetched resources are added to the cache."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        resource_type: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps({"id": "test-id", "resourceType": "Patient"}),
            status=200,
            total_count=1,
            next_url=None,
            resource_type="Patient",
            id_="test-id",
            response_headers=None,
            chunk_number=0,
            cache_hits=0,
            results_by_url=[],
            storage_mode=CompressedDictStorageMode.raw(),
            error=None,
            access_token=None,
            extra_context_to_return=None,
            request_id=None,
            url="http://example.com/fhir/Patient/test-id",
        )

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    result, cache_hits = await processor._get_resources_by_parameters_async(
        id_="test-id",
        resource_type="Patient",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    assert cache_hits == 0
    assert len(result.get_bundle_entries()) == 1
    resource = result.get_bundle_entries()[0].resource
    assert resource is not None
    assert resource.get("id") == "test-id"

    # Verify the resource is now in the cache
    cache_entry = await cache.get_async(resource_type="Patient", resource_id="test-id")
    assert cache_entry is not None
    bundle_entry = cache_entry.bundle_entry
    assert bundle_entry is not None
    resource = bundle_entry.resource
    assert resource is not None
    assert resource.get("id") == "test-id"


@pytest.mark.asyncio
async def test_empty_cache() -> None:
    """Test behavior when the cache is empty."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        resource_type: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps({"id": "test-id", "resourceType": "Patient"}),
            status=200,
            total_count=1,
            next_url=None,
            resource_type="Patient",
            id_="test-id",
            response_headers=None,
            chunk_number=0,
            cache_hits=0,
            results_by_url=[],
            storage_mode=CompressedDictStorageMode.raw(),
            error=None,
            access_token=None,
            extra_context_to_return=None,
            request_id=None,
            url="http://example.com/fhir/Patient/test-id",
        )

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    result, cache_hits = await processor._get_resources_by_parameters_async(
        id_="test-id",
        resource_type="Patient",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    assert cache_hits == 0
    assert len(result.get_bundle_entries()) == 1
    resource = result.get_bundle_entries()[0].resource
    assert resource is not None
    assert resource.get("id") == "test-id"


@pytest.mark.asyncio
async def test_items_added_to_input_cache() -> None:
    """Test that items are appropriately added to the input cache."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    input_cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: Optional[int],
        ids: Optional[List[str]],
        id_above: Optional[str],
        fn_handle_streaming_chunk: Optional[HandleStreamingChunkFunction],
        additional_parameters: Optional[List[str]],
        resource_type: Optional[str],
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps({"id": "test-id", "resourceType": "Patient"}),
            status=200,
            total_count=1,
            next_url=None,
            resource_type="Patient",
            id_="test-id",
            response_headers=None,
            chunk_number=0,
            cache_hits=0,
            results_by_url=[],
            storage_mode=CompressedDictStorageMode.raw(),
            error=None,
            access_token=None,
            extra_context_to_return=None,
            request_id=None,
            url="http://example.com/fhir/Patient/test-id",
        )

    # Mock server response
    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    # Perform the operation
    result, cache_hits = await processor._get_resources_by_parameters_async(
        id_="test-id",
        resource_type="Patient",
        parameters=None,
        cache=input_cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    # Verify the resource is added to the input cache
    cache_entry = await input_cache.get_async(
        resource_type="Patient", resource_id="test-id"
    )
    assert cache_entry is not None
    bundle_entry = cache_entry.bundle_entry
    assert bundle_entry is not None
    resource = bundle_entry.resource
    assert resource is not None
    assert resource.get("id") == "test-id"
    assert cache_hits == 0
    assert len(result.get_bundle_entries()) == 1
    resource = result.get_bundle_entries()[0].resource
    assert resource is not None
    assert resource.get("id") == "test-id"
