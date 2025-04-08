import asyncio
import weakref
from types import TracebackType
from typing import Optional, Type

from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry
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
    ]

    def __init__(self) -> None:
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self._cache: weakref.WeakValueDictionary[str, RequestCacheEntry] = (
            weakref.WeakValueDictionary()
        )
        self._lock: asyncio.Lock = asyncio.Lock()

    async def __aenter__(self) -> "RequestCache":
        """
        This method is called when the RequestCache is entered into a context manager.
        It returns the RequestCache instance.
        """
        async with self._lock:
            self._cache.clear()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        """
        This method is called when the RequestCache is exited from a context manager.
        It clears the cache.
        """
        async with self._lock:
            self._cache.clear()

        if exc_type is not None:
            print(f"An exception of type {exc_type} occurred with message {exc_value}")
            return False  # Propagate any exception that occurred

        return True

    async def get_async(
        self, *, resource_type: str, resource_id: str
    ) -> Optional[RequestCacheEntry]:
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
        bundle_entry: Optional[FhirBundleEntry],
        status: int,
    ) -> bool:
        """
        This method adds the given data to the cache.

        :param resource_type: The resource type to add the cached data for.
        :param resource_id: The resource id to add the cached data for.
        :param status: The status code of the request.
        :param bundle_entry: The cached data to add.
        :return: True if the entry was added, False if it already exists.
        """
        key: str = f"{resource_type}/{resource_id}"

        async with self._lock:
            # Check if the key already exists
            if key in self._cache:
                return False

            # Create the cache entry
            cache_entry = RequestCacheEntry(
                id_=resource_id,
                resource_type=resource_type,
                status=status,
                bundle_entry=bundle_entry,
            )

            # Add to the weak value dictionary
            self._cache[key] = cache_entry

            return True

    async def clear_async(self) -> None:
        """
        This method clears the cache.
        """
        async with self._lock:
            self._cache.clear()
