import json
from typing import (
    Any,
    Optional,
    Dict,
    Deque,
    AsyncGenerator,
    Generator,
    List,
    Tuple,
    OrderedDict,
)

from helix_fhir_client_sdk.fhir.fhir_resource_list import FhirResourceList


class FhirResourceMap:
    """
    FhirResourceMap is a class that represents a map of FHIR resources.
    Each key is a string representing the resource type, and the value is a deque of FhirResource objects.
    """

    __slots__ = [
        "_resource_map",
    ]

    def __init__(
        self,
        initial_dict: Dict[str, FhirResourceList] | None = None,
    ) -> None:
        """
        This class represents a map of FHIR resources, where each key is a string
        and the value is a deque of FhirResource objects.

        :param initial_dict: A dictionary where the keys are strings and the values
        """
        self._resource_map: Dict[str, FhirResourceList] = initial_dict or {}

    def to_dict(self) -> OrderedDict[str, Any]:
        """
        Convert the FhirResourceMap to a dictionary representation.

        """
        result: OrderedDict[str, Any] = OrderedDict[str, Any]()
        for key, value in self._resource_map.items():
            result[key] = [resource.to_dict(remove_nulls=True) for resource in value]
        return result

    def get(self, *, resource_type: str) -> Optional[FhirResourceList]:
        """
        Get the FHIR resources for a specific resource type.

        :param resource_type: The resource type to retrieve.
        :return: A deque of FhirResource objects or None if not found.
        """
        return self._resource_map.get(resource_type, None)

    async def consume_resource_async(
        self,
    ) -> AsyncGenerator[Dict[str, FhirResourceList], None]:
        while self._resource_map:
            # Get the first key
            resource_type: str = next(iter(self._resource_map))
            # Pop and process the item
            resources_for_resource_type: FhirResourceList = self._resource_map.pop(
                resource_type
            )
            yield {
                resource_type: resources_for_resource_type,
            }

    def consume_resource(self) -> Generator[Dict[str, FhirResourceList], None, None]:
        while self._resource_map:
            # Get the first key
            resource_type: str = next(iter(self._resource_map))
            # Pop and process the item
            resources_for_resource_type: FhirResourceList = self._resource_map.pop(
                resource_type
            )
            yield {
                resource_type: resources_for_resource_type,
            }

    def get_resources(self) -> FhirResourceList:
        """
        Get all resources in the map.

        :return: A deque of FhirResource objects.
        """
        resources: FhirResourceList = FhirResourceList()
        for resource_type, resource_list in self._resource_map.items():
            resources.extend(resource_list)
        return resources

    def __setitem__(self, key: str, value: FhirResourceList) -> None:
        """Set the value for a specific key in the resource map."""
        if not isinstance(value, Deque):
            raise TypeError("Value must be a deque of FhirResource objects.")
        self._resource_map[key] = value

    def __getitem__(self, key: str) -> FhirResourceList:
        """Get the value for a specific key in the resource map."""
        return self._resource_map[key]

    def __delitem__(self, key: str) -> None:
        """Delete a key-value pair from the resource map."""
        if key in self._resource_map:
            del self._resource_map[key]
        else:
            raise KeyError(f"Key '{key}' not found in resource map.")

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the resource map."""
        return key in self._resource_map

    def items(self) -> List[Tuple[str, FhirResourceList]]:
        """Get all items in the resource map."""
        return [(k, v) for k, v in self._resource_map.items()]

    def get_resource_count(self) -> int:
        return sum(len(resources) for resources in self._resource_map.values())

    def clear(self) -> None:
        """Clear the resource map."""
        self._resource_map.clear()

    def get_resource_type_and_ids(self) -> List[str]:
        """
        Get the resource type and IDs of the resources in the map.

        :return: A list of strings representing the resource type and IDs.
        """
        resource_type_and_ids: List[str] = []
        for resource_type, resources in self._resource_map.items():
            for resource in resources:
                resource_type_and_ids.append(f"{resource_type}/{resource['id']}")
        return resource_type_and_ids

    def get_operation_outcomes(self) -> FhirResourceList:
        """
        Gets the operation outcomes from the response

        :return: list of operation outcomes
        """
        return (
            self._resource_map["OperationOutcome"]
            if "OperationOutcome" in self._resource_map
            else FhirResourceList()
        )

    def get_resources_except_operation_outcomes(self) -> FhirResourceList:
        """
        Gets the normal FHIR resources by skipping any OperationOutcome resources

        :return: list of valid resources
        """
        combined_resources: FhirResourceList = FhirResourceList()
        for resource_type, resources in self._resource_map.items():
            if resource_type != "OperationOutcome":
                combined_resources.extend(resources)
        return combined_resources

    def to_json(self) -> str:
        """
        Convert the list of FhirResource objects to a JSON string.

        :return: JSON string representation of the list.
        """
        return json.dumps(self.to_dict())

    def get_count_of_resource_types(self) -> int:
        """
        Get the count of unique resource types in the map.

        :return: The count of unique resource types.
        """
        return len(self._resource_map)

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FhirResourceMap":
        """
        Create a copy of the FhirResourceMap.

        :return: A new FhirResourceMap object with the same attributes.
        """
        return FhirResourceMap(initial_dict=self._resource_map.copy())

    def __repr__(self) -> str:
        """
        Return a string representation of the FhirResourceMap.

        :return: String representation of the FhirResourceMap.
        """
        return f"FhirResourceMap(keys: {len(self._resource_map.keys())})"
