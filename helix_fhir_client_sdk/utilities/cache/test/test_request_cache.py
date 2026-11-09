import pytest

from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache


async def _cache_with(resource_type: str, resource_id: str) -> RequestCache:
    cache = RequestCache(clear_cache_at_the_end=False)
    await cache.add_async(
        resource_type=resource_type,
        resource_id=resource_id,
        bundle_entry=None,
        status=200,
        last_modified=None,
        etag=None,
        from_input_cache=False,
        raw_hash="h",
    )
    return cache


@pytest.mark.asyncio
async def test_get_async_counts_hits_and_misses() -> None:
    cache = await _cache_with("Patient", "p1")

    assert await cache.get_async(resource_type="Patient", resource_id="p1") is not None
    assert await cache.get_async(resource_type="Patient", resource_id="missing") is None

    assert cache.cache_hits == 1
    assert cache.cache_misses == 1


@pytest.mark.asyncio
async def test_peek_async_does_not_count_hits_or_misses() -> None:
    """Existence checks made for bookkeeping must not distort the hit/miss counters."""
    cache = await _cache_with("Patient", "p1")

    assert await cache.peek_async(resource_type="Patient", resource_id="p1") is not None
    assert await cache.peek_async(resource_type="Patient", resource_id="missing") is None

    assert cache.cache_hits == 0
    assert cache.cache_misses == 0
