import copy
import json
from contextlib import contextmanager
from typing import Deque, List, AsyncGenerator, Optional, Any, Dict, Iterator

from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class BaseResourceList[T: CompressedDict[str, Any]](Deque[T]):
    """
    Represents a list of FHIR resources.
    """

    __slots__: List[str] = []

    def to_json(self) -> str:
        """
        Convert the list of FhirResource objects to a JSON string.

        :return: JSON string representation of the list.
        """
        return json.dumps([r.to_dict() for r in self], cls=FhirJSONEncoder)

    def get_resources(self) -> "BaseResourceList[T]":
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
    ) -> AsyncGenerator["BaseResourceList[T]", None]:
        """
        Consume resources in batches asynchronously.

        :param batch_size: The size of each batch.
        :return: An async generator yielding batches of FhirResourceList.
        """
        if batch_size is None:
            while self:
                yield BaseResourceList[T]([self.popleft()])
        elif batch_size <= 0:
            raise ValueError("Batch size must be greater than 0.")
        else:
            while self:
                batch = BaseResourceList[T]()
                for _ in range(min(batch_size, len(self))):
                    batch.append(self.popleft())
                yield batch

    def __deepcopy__(self, memo: Dict[int, Any]) -> "BaseResourceList[T]":
        """
        Create a copy of the FhirResourceList.

        :return: A new FhirResourceList object with the same resources.
        """
        return BaseResourceList[T]([copy.deepcopy(r) for r in self])

    def __repr__(self) -> str:
        """
        Return a string representation of the FhirResourceList.

        :return: A string representation of the FhirResourceList.
        """
        return f"FhirResourceList(resources: {len(self)})"

    @contextmanager
    def transaction(self) -> Iterator["BaseResourceList[T]"]:
        """
        Opens a transaction for all resources in the list.

        Deserializes the dictionary before entering the context
        Serializes the dictionary after exiting the context

        Raises:
            CompressedDictAccessError: If methods are called outside the context

        """
        try:
            self.start_transaction()

            yield self

        finally:
            self.end_transaction()

    def start_transaction(self) -> "BaseResourceList[T]":
        """
        Starts a transaction for each resource in the list.  Use transaction() for a contextmanager for simpler usage.
        """

        for resource in self:
            resource.start_transaction()
        return self

    def end_transaction(self) -> "BaseResourceList[T]":
        """
        Ends a transaction.  Use transaction() for a context_manager for simpler usage.

        """
        for resource in self:
            resource.end_transaction()
        return self
