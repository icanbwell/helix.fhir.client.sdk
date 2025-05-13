import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from types import TracebackType
from typing import Any

from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry

from helix_fhir_client_sdk.utilities.cache.request_cache_entry import RequestCacheEntry


class RequestCache:
    """
    This is a class that caches requests to the FHIR server using a weak value dictionary.
    It is used to avoid multiple requests to the FHIR server when doing a large number
    of requests for the same resource.
    """

    __slots__ = [
        "cache_hits",
        "cache_misses",
        "_cache",
        "_lock",
        "_clear_cache_at_the_end",
    ]

    def __init__(
        self,
        *,
        initial_dict: dict[str, Any] | None = None,
        clear_cache_at_the_end: bool | None = True,
    ) -> None:
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self._cache: dict[str, RequestCacheEntry] = initial_dict or {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._clear_cache_at_the_end: bool | None = clear_cache_at_the_end

    async def __aenter__(self) -> "RequestCache":
        """
        This method is called when the RequestCache is entered into a context manager.
        It returns the RequestCache instance.
        """
        if self._clear_cache_at_the_end:
            async with self._lock:
                self._cache.clear()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """
        This method is called when the RequestCache is exited from a context manager.
        It clears the cache.
        """
        if self._clear_cache_at_the_end:
            async with self._lock:
                self._cache.clear()

        if exc_value is not None:
            raise exc_value.with_traceback(traceback)

        return True

    async def get_async(self, *, resource_type: str, resource_id: str) -> RequestCacheEntry | None:
        """
        This method returns the cached data for a given URL, or None if the URL is not in the cache.

        :param resource_type: The resource type to get the cached data for.
        :param resource_id: The resource id to get the cached data for.
        :return: The cached data for the given resource type and resource id, or None if the data is not in the cache.
        """
        key: str = f"{resource_type}/{resource_id}"

        async with self._lock:
            cached_entry = self._cache.get(key)

            if cached_entry is not None:
                self.cache_hits += 1
                return cached_entry

            self.cache_misses += 1
            return None

    async def add_async(
        self,
        *,
        resource_type: str,
        resource_id: str,
        bundle_entry: FhirBundleEntry | None,
        status: int,
        last_modified: datetime | None,
        etag: str | None,
        from_input_cache: bool | None | None,
        raw_hash: str,
    ) -> bool:
        """
        This method adds the given data to the cache.

        :param resource_type: The resource type to add the cached data for.
        :param resource_id: The resource id to add the cached data for.
        :param status: The status code of the request.
        :param bundle_entry: The cached data to add.
        :param last_modified: The last updated date of the resource.
        :param etag: The ETag of the resource.
        :param from_input_cache: Whether the entry was added from the input cache.
        :return: True if the entry was added, False if it already exists.
        """
        key: str = f"{resource_type}/{resource_id}"

        async with self._lock:
            # Create the cache entry
            cache_entry = RequestCacheEntry(
                id_=resource_id,
                resource_type=resource_type,
                status=status,
                bundle_entry=bundle_entry,
                last_modified=last_modified,
                etag=etag,
                from_input_cache=from_input_cache,
                raw_hash=raw_hash,
            )

            # Add to the weak value dictionary
            self._cache[key] = cache_entry

            return True

    async def remove_async(self, *, resource_key: str) -> bool:
        """
        This method remove the given data from the cache.
        :param resource_key: resource key contains both resourceType and resourceId. Eg: Patient/123
        """
        async with self._lock:
            if resource_key not in self._cache:
                return False

            del self._cache[resource_key]

            return True

    async def clear_async(self) -> None:
        """
        This method clears the cache.
        """
        async with self._lock:
            self._cache.clear()

    async def get_entries_async(self) -> AsyncGenerator[RequestCacheEntry, None]:
        """
        This method returns the entries in the cache.

        :return: The keys in the cache.
        """
        async with self._lock:
            for entry in self._cache.values():
                yield entry

    async def get_keys_async(self) -> list[str]:
        """
        This method returns the keys in the cache.

        :return: The entries in the cache.
        """
        async with self._lock:
            return list(self._cache.keys())

    def __len__(self) -> int:
        """
        This method returns the number of entries in the cache.

        :return: The number of entries in the cache.
        """
        return len(self._cache)

    def __repr__(self) -> str:
        """
        This method returns a string representation of the cache.

        :return: A string representation of the cache.
        """
        return f"RequestCache(cache_size={len(self._cache)})"
