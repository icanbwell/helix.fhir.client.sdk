from typing import (
    List,
    Set,
    Optional,
    AsyncGenerator,
    cast,
    Generator,
    Dict,
    override,
    Iterable,
)

from helix_fhir_client_sdk.fhir.base_resource_list import BaseResourceList
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource


class FhirResourceList(BaseResourceList[FhirResource]):
    """
    Represents a list of FHIR resources.
    """

    __slots__: List[str] = BaseResourceList.__slots__

    def get_resource_type_and_ids(self) -> List[str]:
        """
        Get the resource type and IDs of the resources in the list.

        :return: A list of strings representing the resource type and IDs.
        """
        resource_type_and_ids: List[str] = []
        for resource in self:
            resource_type_and_ids.append(f"{resource.resource_type}/{resource.id}")
        return resource_type_and_ids

    def get_operation_outcomes(self) -> "FhirResourceList":
        """
        Gets the operation outcomes from the response

        :return: list of operation outcomes
        """
        return FhirResourceList(
            [r for r in self if r.resource_type == "OperationOutcome"]
        )

    def get_resources_except_operation_outcomes(self) -> "FhirResourceList":
        """
        Gets the normal FHIR resources by skipping any OperationOutcome resources

        :return: list of valid resources
        """
        return FhirResourceList(
            [r for r in self if r.resource_type != "OperationOutcome"]
        )

    def remove_duplicates(self) -> None:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """

        # remove duplicates from the list if they have the same resourceType and id
        seen: Set[str] = set()
        i = 0
        while i < len(self):
            # Create a tuple of values for specified keys
            comparison_key = self[i].resource_type_and_id

            if not comparison_key:
                # Skip if resourceType or id is None
                i += 1
                continue

            if comparison_key in seen or self[i].id is None:
                # Remove duplicate entry
                self.remove(self[i])
            else:
                seen.add(comparison_key)
                i += 1

    async def consume_resource_batch_async(
        self,
        *,
        batch_size: Optional[int],
    ) -> AsyncGenerator["FhirResourceList", None]:
        async for r in super().consume_resource_batch_async(batch_size=batch_size):
            yield cast(FhirResourceList, r)

    def consume_resource_batch(
        self,
        *,
        batch_size: Optional[int],
    ) -> Generator["FhirResourceList", None, None]:
        for r in super().consume_resource_batch(batch_size=batch_size):
            yield cast(FhirResourceList, r)

    def get_count_by_resource_type(self) -> Dict[str, int]:
        """
        Gets the count of resources by resource type.

        :return: The count of resources by resource type
        """
        resources_by_type: Dict[str, int] = dict()
        if len(self) == 0:
            return resources_by_type

        entry: FhirResource
        for resource in [r for r in self if r is not None]:
            resource_type: str = resource.resource_type or "unknown"
            if resource_type not in resources_by_type:
                resources_by_type[resource_type] = 0
            resources_by_type[resource_type] += 1
        return resources_by_type

    @override
    def append(self, x: FhirResource, /) -> None:
        """
        Append an entry to the FhirBundleEntryList.

        :param x: The entry to append.
        """
        if not isinstance(x, FhirResource):
            raise TypeError("Only FhirBundleEntry instances can be appended.")

        # check that we don't have a duplicate entry
        key: Optional[str] = x.resource_type_and_id
        if key is None:
            super().append(x)
        else:
            for entry in self:
                if entry.resource_type_and_id == key:
                    # we have a duplicate entry
                    return
            super().append(x)

    @override
    def extend(self, iterable: Iterable[FhirResource], /) -> None:
        """
        Extend the FhirBundleEntryList with entries from an iterable.

        :param iterable: The iterable containing entries to extend.
        """
        for entry in iterable:
            self.append(entry)
