import asyncio
from types import TracebackType
from typing import Dict, Optional, Type

from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry
from helix_fhir_client_sdk.utilities.cache.request_cache_entry import RequestCacheEntry


class RequestCache:
    """
    This is a class that caches requests to the FHIR server. It is used to avoid multiple requests to the FHIR server
    when we are doing a large number of requests for the same resource. It is used in the following way:

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
        self._cache: Dict[str, RequestCacheEntry] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def __aenter__(self) -> "RequestCache":
        """
        This method is called when the RequestCache is entered into a context manager. It returns the RequestCache
        instance.
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
        This method is called when the RequestCache is exited from a context manager. It clears the cache.
        """
        async with self._lock:
            self._cache.clear()
        if exc_type is not None:
            print(f"An exception of type {exc_type} occurred with message {exc_value}")
            return False  # Propagate any exception that occurred
        else:
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
            if key in self._cache:
                self.cache_hits += 1
                return self._cache[key]

            self.cache_misses += 1
            return None

    async def add_async(
        self,
        *,
        resource_type: str,
        resource_id: str,
        bundle_entry: FhirBundleEntry | None,
        status: int,
    ) -> bool:
        """
        This method adds the given data to the cache.


        :param resource_type: The resource type to add the cached data for.
        :param resource_id: The resource id to add the cached data for.
        :param status: The status code of the request.
        :param bundle_entry: The cached data to add.
        """
        key: str = f"{resource_type}/{resource_id}"
        cache_entry = RequestCacheEntry(
            id_=resource_id,
            resource_type=resource_type,
            status=status,
            bundle_entry=bundle_entry,
        )

        async with self._lock:
            if key not in self._cache:
                self._cache[key] = cache_entry
                return True
            else:
                return False

    async def clear_async(self) -> None:
        """
        This method clears the cache.
        """
        async with self._lock:
            self._cache.clear()
