import json
from collections.abc import Awaitable, Callable
from logging import getLogger

import pytest
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import CompressedDictStorageMode

from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import FhirGetBundleResponse
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache


async def _add(cache: RequestCache, resource_id: str, *, from_input_cache: bool) -> None:
    await cache.add_async(
        resource_type="Practitioner",
        resource_id=resource_id,
        bundle_entry=None,
        status=200,
        last_modified=None,
        etag=None,
        from_input_cache=from_input_cache,
        raw_hash="",
    )


async def _add_input(cache: RequestCache) -> None:
    await _add(cache, "1", from_input_cache=True)


async def _add_fetched(cache: RequestCache) -> None:
    await _add(cache, "1", from_input_cache=False)


async def _add_input_then_overwrite(cache: RequestCache) -> None:
    await _add(cache, "1", from_input_cache=True)
    await _add(cache, "1", from_input_cache=False)


async def _add_input_then_remove(cache: RequestCache) -> None:
    await _add(cache, "1", from_input_cache=True)
    await cache.remove_async(resource_key="Practitioner/1")


async def _add_input_then_clear(cache: RequestCache) -> None:
    await _add(cache, "1", from_input_cache=True)
    await cache.clear_async()


async def _add_two_inputs_remove_one(cache: RequestCache) -> None:
    await _add(cache, "1", from_input_cache=True)
    await _add(cache, "2", from_input_cache=True)
    await cache.remove_async(resource_key="Practitioner/1")


@pytest.mark.parametrize(
    "steps,expected",
    [
        (_add_input, True),
        (_add_fetched, False),
        (_add_input_then_overwrite, False),
        (_add_input_then_remove, False),
        (_add_input_then_clear, False),
        (_add_two_inputs_remove_one, True),
    ],
    ids=[
        "input-entry",
        "fetched-entry",
        "input-entry-overwritten-by-fetch",
        "input-entry-removed",
        "cache-cleared",
        "one-of-two-input-entries-removed",
    ],
)
@pytest.mark.asyncio
async def test_has_input_cache_entries_tracks_input_entries(
    steps: Callable[[RequestCache], Awaitable[None]], expected: bool
) -> None:
    # Arrange
    cache = RequestCache(clear_cache_at_the_end=False)

    # Act
    await steps(cache)

    # Assert
    assert cache.has_input_cache_entries() is expected


def _bundle_response(resource_ids: list[str]) -> FhirGetBundleResponse:
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": {"resourceType": "Practitioner", "id": i}} for i in resource_ids],
    }
    return FhirGetBundleResponse(
        request_id=None,
        url="https://example.com/Practitioner",
        response_text=json.dumps(bundle),
        error=None,
        access_token=None,
        total_count=None,
        status=200,
        extra_context_to_return=None,
        resource_type="Practitioner",
        id_=None,
        response_headers=None,
        results_by_url=[],
        storage_mode=CompressedDictStorageMode.default(),
    )


@pytest.mark.parametrize(
    "input_cache_ids,fetched_ids,bundle_ids,expected_remaining",
    [
        ([], ["1", "2"], ["1", "2"], ["1", "2"]),
        (["1"], ["2"], ["1", "2", "3"], ["2", "3"]),
    ],
    ids=["no-input-cache-keeps-everything", "input-cache-entry-removed"],
)
@pytest.mark.asyncio
async def test_remove_entries_in_cache_only_removes_input_cache_entries(
    input_cache_ids: list[str], fetched_ids: list[str], bundle_ids: list[str], expected_remaining: list[str]
) -> None:
    # Arrange
    cache = RequestCache(clear_cache_at_the_end=False)
    for resource_id in input_cache_ids:
        await _add(cache, resource_id, from_input_cache=True)
    for resource_id in fetched_ids:
        await _add(cache, resource_id, from_input_cache=False)
    bundle_response = _bundle_response(bundle_ids)

    # Act
    await bundle_response.remove_entries_in_cache_async(
        request_cache=cache, compare_hash=False, logger=getLogger(__name__)
    )

    # Assert
    remaining = sorted(str(e.resource.id) for e in bundle_response.get_bundle_entries() if e.resource)
    assert remaining == expected_remaining


class _CacheSkippingInit(RequestCache):
    """Like a subclass that skips RequestCache.__init__, or a cache unpickled from an older SDK."""

    def __init__(self) -> None:
        self.cache_hits = 0
        self.cache_misses = 0
        self._cache = {}


@pytest.mark.parametrize("from_input_cache", [True, False], ids=["input-entry", "fetched-entry"])
@pytest.mark.asyncio
async def test_has_input_cache_entries_without_request_cache_init(from_input_cache: bool) -> None:
    # Arrange
    cache = _CacheSkippingInit()

    # Act
    await _add(cache, "1", from_input_cache=from_input_cache)
    await cache.remove_async(resource_key="Practitioner/2")

    # Assert
    assert cache.has_input_cache_entries() is from_input_cache
