from collections import deque
from typing import Any, Optional, Dict, Deque, AsyncGenerator, Generator

from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource


class FhirResourceMap:
    def __init__(
        self,
        *,
        initial_dict: Dict[str, Deque[FhirResource]] | None = None,
    ) -> None:
        """
        This class represents a map of FHIR resources, where each key is a string
        and the value is a deque of FhirResource objects.

        :param initial_dict: A dictionary where the keys are strings and the values
        """
        self._resource_map: Dict[str, Deque[FhirResource]] = initial_dict or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the FhirResourceMap to a dictionary representation.

        """
        result: Dict[str, Any] = {}
        for key, value in self._resource_map.items():
            result[key] = [resource.to_dict() for resource in value]
        return result

    def get(self, *, resource_type: str) -> Optional[Deque[FhirResource]]:
        """
        Get the FHIR resources for a specific resource type.

        :param resource_type: The resource type to retrieve.
        :return: A deque of FhirResource objects or None if not found.
        """
        return self._resource_map.get(resource_type, None)

    async def consume_resource_async(
        self,
    ) -> AsyncGenerator[Dict[str, Deque[FhirResource]], None]:
        while self._resource_map:
            # Get the first key
            resource_type: str = next(iter(self._resource_map))
            # Pop and process the item
            resources_for_resource_type: Deque[FhirResource] = self._resource_map.pop(
                resource_type
            )
            yield {
                resource_type: resources_for_resource_type,
            }

    def consume_resource(self) -> Generator[Dict[str, Deque[FhirResource]], None, None]:
        while self._resource_map:
            # Get the first key
            resource_type: str = next(iter(self._resource_map))
            # Pop and process the item
            resources_for_resource_type: Deque[FhirResource] = self._resource_map.pop(
                resource_type
            )
            yield dict(
                resource_type=resource_type,
                resources=resources_for_resource_type,
            )

    def get_resources(self) -> Deque[FhirResource]:
        """
        Get all resources in the map.

        :return: A deque of FhirResource objects.
        """
        resources: Deque[FhirResource] = deque()
        for resource_type, resource_list in self._resource_map.items():
            resources.extend(resource_list)
        return resources

    def __setitem__(self, key: str, value: Deque[FhirResource]) -> None:
        """Set the value for a specific key in the resource map."""
        if not isinstance(value, Deque):
            raise TypeError("Value must be a deque of FhirResource objects.")
        self._resource_map[key] = value

    def __getitem__(self, key: str) -> Deque[FhirResource]:
        """Get the value for a specific key in the resource map."""
        return self._resource_map[key]

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the resource map."""
        return key in self._resource_map

    def items(self) -> Dict[str, deque[FhirResource]]:
        """Get all items in the resource map."""
        return {k: v for k, v in self._resource_map.items()}

    def get_resource_count(self) -> int:
        return sum(len(resources) for resources in self._resource_map.values())

    def clear(self) -> None:
        """Clear the resource map."""
        self._resource_map.clear()
