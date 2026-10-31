import json
from collections.abc import AsyncGenerator
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
from helix_fhir_client_sdk.responses.get.fhir_get_error_response import (
    FhirGetErrorResponse,
)
from helix_fhir_client_sdk.responses.get.fhir_get_single_response import (
    FhirGetSingleResponse,
)
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache
from helix_fhir_client_sdk.utilities.hash_util import ResourceHash


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
    mock_entry = FhirBundleEntry(resource=FhirResource({"id": "test-id", "resourceType": "Patient"}))
    await cache.add_async(
        resource_type="Patient",
        resource_id="test-id",
        bundle_entry=mock_entry,
        status=200,
        last_modified=None,
        etag=None,
        from_input_cache=False,
        raw_hash=ResourceHash().hash_value(json.dumps(json.loads(mock_entry._resource.json()), sort_keys=True))
        if mock_entry._resource
        else "",
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
    assert len(result.get_bundle_entries()) == 0


@pytest.mark.asyncio
async def test_cache_miss() -> None:
    """Test that resources are fetched from the server when not in the cache."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
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
    mock_entry = FhirBundleEntry(resource=FhirResource({"id": "cached-id", "resourceType": "Patient"}))
    await cache.add_async(
        resource_type="Patient",
        resource_id="cached-id",
        bundle_entry=mock_entry,
        status=200,
        last_modified=None,
        etag=None,
        from_input_cache=False,
        raw_hash=ResourceHash().hash_value(json.dumps(json.loads(mock_entry._resource.json()), sort_keys=True))
        if mock_entry._resource
        else "",
    )

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps({"id": "non-cached-id", "resourceType": "Patient"}),
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
    resource_ids = [entry.resource.get("id") for entry in result.get_bundle_entries() if entry.resource]
    assert set(resource_ids) == {"non-cached-id"}


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
        from_input_cache=False,
        raw_hash="",
    )

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps({"id": "non-cached-id", "resourceType": "Patient"}),
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
    resource_ids = [entry.resource.get("id") for entry in result.get_bundle_entries() if entry.resource]
    assert set(resource_ids) == {"non-cached-id"}


@pytest.mark.asyncio
async def test_cache_update() -> None:
    """Test that fetched resources are added to the cache."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
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
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
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
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
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
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    # Verify the resource is added to the input cache
    cache_entry = await cache.get_async(resource_type="Patient", resource_id="test-id")
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


def _error_response(*, status: int, ids: list[str] | None) -> FhirGetErrorResponse:
    return FhirGetErrorResponse(
        request_id=None,
        url="http://example.com/fhir/Practitioner",
        response_text="",
        error=f"server returned {status}",
        access_token=None,
        total_count=0,
        status=status,
        next_url=None,
        extra_context_to_return=None,
        resource_type="Practitioner",
        id_=ids,
        response_headers=None,
        chunk_number=0,
        cache_hits=0,
        results_by_url=[],
        storage_mode=CompressedDictStorageMode.raw(),
        create_operation_outcome_for_error=None,
    )


@pytest.mark.asyncio
async def test_failed_single_id_fetch_is_cached_with_its_status_not_404() -> None:
    """A failed fetch is cached with its own status, not as 404."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield _error_response(status=500, ids=ids)

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    await processor._get_resources_by_parameters_async(
        id_="p1",
        resource_type="Practitioner",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    entry = await cache.get_async(resource_type="Practitioner", resource_id="p1")
    assert entry is not None
    assert entry.status == 500


@pytest.mark.asyncio
async def test_failed_batch_then_one_by_one_fetch_keeps_each_ids_failure_status() -> None:
    """Statuses recorded by the one-by-one fallback are not overwritten with 404."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield _error_response(status=503, ids=ids)

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    await processor._get_resources_by_parameters_async(
        id_=["p1", "p2"],
        resource_type="Practitioner",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    # the not-found pass must not count as cache reuse: the only lookups were the
    # initial misses for p1 and p2 (by-param pass, then one-by-one pass)
    assert cache.cache_hits == 0
    assert cache.cache_misses == 4

    for resource_id in ("p1", "p2"):
        entry = await cache.get_async(resource_type="Practitioner", resource_id=resource_id)
        assert entry is not None, resource_id
        assert entry.status == 503, resource_id


@pytest.mark.asyncio
async def test_id_missing_from_successful_batch_is_still_cached_as_404() -> None:
    """A successful batch that simply does not contain an id is a genuine not-found."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        yield FhirGetSingleResponse(
            response_text=json.dumps({"id": "p1", "resourceType": "Practitioner"}),
            status=200,
            total_count=1,
            next_url=None,
            resource_type="Practitioner",
            id_="p1",
            response_headers=None,
            chunk_number=0,
            cache_hits=0,
            results_by_url=[],
            storage_mode=CompressedDictStorageMode.raw(),
            error=None,
            access_token=None,
            extra_context_to_return=None,
            request_id=None,
            url="http://example.com/fhir/Practitioner?_id=p1,p2",
        )

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    await processor._get_resources_by_parameters_async(
        id_=["p1", "p2"],
        resource_type="Practitioner",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    found = await cache.get_async(resource_type="Practitioner", resource_id="p1")
    missing = await cache.get_async(resource_type="Practitioner", resource_id="p2")
    assert found is not None and found.status == 200
    assert missing is not None and missing.status == 404


@pytest.mark.asyncio
async def test_one_by_one_fallback_with_mixed_results_keeps_each_ids_own_status() -> None:
    """Per-id statuses from the one-by-one fallback win over the aggregate response status."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        if ids == ["p1"]:
            yield FhirGetSingleResponse(
                response_text=json.dumps({"id": "p1", "resourceType": "Practitioner"}),
                status=200,
                total_count=1,
                next_url=None,
                resource_type="Practitioner",
                id_="p1",
                response_headers=None,
                chunk_number=0,
                cache_hits=0,
                results_by_url=[],
                storage_mode=CompressedDictStorageMode.raw(),
                error=None,
                access_token=None,
                extra_context_to_return=None,
                request_id=None,
                url="http://example.com/fhir/Practitioner/p1",
            )
        else:
            # the ?_id=p1,p2 batch and the one-by-one fetch of p2 both fail
            yield _error_response(status=503, ids=ids)

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    await processor._get_resources_by_parameters_async(
        id_=["p1", "p2"],
        resource_type="Practitioner",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    found = await cache.get_async(resource_type="Practitioner", resource_id="p1")
    failed = await cache.get_async(resource_type="Practitioner", resource_id="p2")
    assert found is not None and found.status == 200
    assert failed is not None and failed.status == 503


@pytest.mark.asyncio
async def test_one_by_one_fallback_absent_id_is_404_even_when_another_id_failed() -> None:
    """An id that fetched successfully but returned nothing is not found (404), whatever happened to other ids."""
    processor = MockSimulatedGraphProcessor()  # type: ignore[abstract]
    cache = RequestCache()

    # noinspection PyUnusedLocal
    async def mock_async_generator(
        page_number: int | None,
        ids: list[str] | None,
        id_above: str | None,
        fn_handle_streaming_chunk: HandleStreamingChunkFunction | None,
        additional_parameters: list[str] | None,
        resource_type: str | None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
        if ids == ["p2"]:
            # success with no resource: genuinely absent
            yield FhirGetSingleResponse(
                response_text="",
                status=200,
                total_count=0,
                next_url=None,
                resource_type="Practitioner",
                id_="p2",
                response_headers=None,
                chunk_number=0,
                cache_hits=0,
                results_by_url=[],
                storage_mode=CompressedDictStorageMode.raw(),
                error=None,
                access_token=None,
                extra_context_to_return=None,
                request_id=None,
                url="http://example.com/fhir/Practitioner/p2",
            )
        else:
            # the ?_id=p1,p2 batch and the one-by-one fetch of p1 both fail
            yield _error_response(status=500, ids=ids)

    processor._get_with_session_async = mock_async_generator  # type: ignore[method-assign]

    await processor._get_resources_by_parameters_async(
        id_=["p1", "p2"],
        resource_type="Practitioner",
        parameters=None,
        cache=cache,
        scope_parser=MagicMock(scope_allows=MagicMock(return_value=True)),
        logger=None,
        id_search_unsupported_resources=[],
    )

    failed = await cache.get_async(resource_type="Practitioner", resource_id="p1")
    absent = await cache.get_async(resource_type="Practitioner", resource_id="p2")
    assert failed is not None and failed.status == 500
    assert absent is not None and absent.status == 404
