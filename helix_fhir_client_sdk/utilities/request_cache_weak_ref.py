from types import TracebackType
from typing import Dict, Optional, Type
import weakref
from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry


class RequestCacheWeakRef:
    """
    A memory-efficient request cache using weak references to allow
    garbage collection of cached entries when they're no longer used elsewhere.

    Uses weak references to prevent holding onto objects that are no longer
    referenced elsewhere in the application.
    """

    __slots__ = [
        "cache_hits",
        "cache_misses",
        "_cache",
    ]

    def __init__(self) -> None:
        """
        Initialize the request cache with hit/miss tracking.
        Uses a weak value dictionary to allow garbage collection.
        """
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        # Use weak value dictionary to allow automatic cleanup
        self._cache: Dict[str, weakref.ReferenceType[FhirBundleEntry]] = {}

    def __enter__(self) -> "RequestCacheWeakRef":
        """
        Context manager entry method.

        Returns:
            RequestCache: The current cache instance
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        """
        Context manager exit method.
        Clears the cache and handles any exceptions.

        Returns:
            Optional[bool]: Whether to suppress the exception
        """
        self.clear()

        if exc_type is not None:
            print(f"An exception of type {exc_type} occurred with message {exc_value}")
            return False  # Propagate the exception

        return True

    def get(self, *, resource_type: str, resource_id: str) -> Optional[FhirBundleEntry]:
        """
        Retrieve a cached entry, with hit/miss tracking.

        Args:
            resource_type (str): The type of FHIR resource
            resource_id (str): The ID of the specific resource

        Returns:
            Optional[FhirBundleEntry]: The cached entry or None
        """
        key: str = f"{resource_type}/{resource_id}"

        # Attempt to retrieve the weak reference
        weak_ref = self._cache.get(key)

        if weak_ref is not None:
            # Attempt to get the actual object from the weak reference
            cached_entry = weak_ref()

            if cached_entry is not None:
                self.cache_hits += 1
                return cached_entry
            else:
                # Weak reference has been garbage collected
                del self._cache[key]

        self.cache_misses += 1
        return None

    def add(
        self, *, resource_type: str, resource_id: str, bundle_entry: FhirBundleEntry
    ) -> None:
        """
        Add an entry to the cache using a weak reference.

        Args:
            resource_type (str): The type of FHIR resource
            resource_id (str): The ID of the specific resource
            bundle_entry (FhirBundleEntry): The entry to cache
        """
        key: str = f"{resource_type}/{resource_id}"

        # Create a weak reference to the bundle entry
        self._cache[key] = weakref.ref(bundle_entry)

    def clear(self) -> None:
        """
        Clear the entire cache.
        """
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """
        Get the current number of entries in the cache.

        Returns:
            int: Number of cache entries
        """
        return len(self._cache)
