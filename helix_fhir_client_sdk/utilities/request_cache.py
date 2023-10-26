from types import TracebackType
from typing import Dict, Optional, Type

from helix_fhir_client_sdk.fhir_bundle import BundleEntry


class RequestCache:
    """
    This is a class that caches requests to the FHIR server. It is used to avoid multiple requests to the FHIR server
    when we are doing a large number of requests for the same resource. It is used in the following way:

    """

    def __enter__(self) -> "RequestCache":
        """
        This method is called when the RequestCache is entered into a context manager. It returns the RequestCache
        instance.
        """
        self._cache: Dict[str, BundleEntry] = {}
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        """
        This method is called when the RequestCache is exited from a context manager. It clears the cache.
        """
        self._cache.clear()
        if exc_type is not None:
            print(f"An exception of type {exc_type} occurred with message {exc_value}")
            return False  # Propagate any exception that occurred
        else:
            return True

    def __init__(self) -> None:
        self.cache_hits: int = 0
        self.cache_misses: int = 0

    def get(self, *, resource_type: str, resource_id: str) -> Optional[BundleEntry]:
        """
        This method returns the cached data for a given URL, or None if the URL is not in the cache.


        :param resource_type: The resource type to get the cached data for.
        :param resource_id: The resource id to get the cached data for.
        :return: The cached data for the given resource type and resource id, or None if the data is not in the cache.
        """
        key: str = f"{resource_type}/{resource_id}"
        if key in self._cache:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        return self._cache.get(key)

    def add(
        self, *, resource_type: str, resource_id: str, bundle_entry: BundleEntry
    ) -> None:
        """
        This method adds the given data to the cache.


        :param resource_type: The resource type to add the cached data for.
        :param resource_id: The resource id to add the cached data for.
        :param bundle_entry: The cached data to add.
        """
        key: str = f"{resource_type}/{resource_id}"
        self._cache[key] = bundle_entry

    def clear(self) -> None:
        """
        This method clears the cache.
        """
        self._cache.clear()
