import json
from typing import Deque, List, Set, AsyncGenerator, Optional

from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class FhirResourceList(Deque[FhirResource]):
    __slots__: List[str] = []

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

    def to_json(self) -> str:
        """
        Convert the list of FhirResource objects to a JSON string.

        :return: JSON string representation of the list.
        """
        return json.dumps([r.to_dict() for r in self], cls=FhirJSONEncoder)

    def get_resources(self) -> "FhirResourceList":
        """
        Get all resources in the list.

        :return: A list of FhirResource objects.
        """
        # this is here to keep compatibility with FhirResourceMap
        return self

    async def consume_resource_async(
        self,
        *,
        batch_size: Optional[int],
    ) -> AsyncGenerator["FhirResourceList", None]:
        """
        Consume resources in batches asynchronously.

        :param batch_size: The size of each batch.
        :return: An async generator yielding batches of FhirResourceList.
        """
        if batch_size is None:
            while self:
                yield FhirResourceList([self.popleft()])
        elif batch_size <= 0:
            raise ValueError("Batch size must be greater than 0.")
        else:
            while self:
                batch = FhirResourceList()
                for _ in range(min(batch_size, len(self))):
                    batch.append(self.popleft())
                yield batch

    def copy(self) -> "FhirResourceList":
        """
        Create a copy of the FhirResourceList.

        :return: A new FhirResourceList object with the same resources.
        """
        return FhirResourceList([r.copy() for r in self])
