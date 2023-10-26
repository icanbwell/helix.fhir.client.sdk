from typing import Dict, Any, Optional


class RequestCache:
    """
    This is a class that caches requests to the FHIR server. It is used to avoid multiple requests to the FHIR server
    when we are doing a large number of requests for the same resource. It is used in the following way:

    """

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, *, resource_type: str, resource_id: str) -> Optional[Dict[str, Any]]:
        """
        This method returns the cached data for a given URL, or None if the URL is not in the cache.


        :param resource_type: The resource type to get the cached data for.
        :param resource_id: The resource id to get the cached data for.
        :return: The cached data for the given resource type and resource id, or None if the data is not in the cache.
        """
        key: str = f"{resource_type}/{resource_id}"
        return self._cache.get(key)

    def add(
        self, *, resource_type: str, resource_id: str, data: Dict[str, Any]
    ) -> None:
        """
        This method adds the given data to the cache.


        :param resource_type: The resource type to add the cached data for.
        :param resource_id: The resource id to add the cached data for.
        :param data: The data to add to the cache.
        """
        key: str = f"{resource_type}/{resource_id}"
        self._cache[key] = data

    def clear(self) -> None:
        """
        This method clears the cache.
        """
        self._cache.clear()
