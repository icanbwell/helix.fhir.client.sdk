import copy
from typing import Deque, Optional, AsyncGenerator, List, Any, Dict, override, Iterable

from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry


class FhirBundleEntryList(Deque[FhirBundleEntry]):
    """
    Represents a list of FHIR Bundle entries.
    """

    __slots__: List[str] = []

    async def consume_resource_async(
        self,
        *,
        batch_size: Optional[int],
    ) -> AsyncGenerator["FhirBundleEntryList", None]:
        """
        Consume bundle entries in batches asynchronously.

        :param batch_size: The size of each batch.
        :return: An async generator yielding batches of FhirResourceList.
        """
        if batch_size is None:
            while self:
                yield FhirBundleEntryList([self.popleft()])
        elif batch_size <= 0:
            raise ValueError("Batch size must be greater than 0.")
        else:
            while self:
                batch = FhirBundleEntryList()
                for _ in range(min(batch_size, len(self))):
                    batch.append(self.popleft())
                yield batch

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FhirBundleEntryList":
        """
        Create a shallow copy of the FhirBundleEntryList.

        :return: A new FhirBundleEntryList instance with the same entries.
        """
        return FhirBundleEntryList([copy.deepcopy(entry) for entry in self])

    def __repr__(self) -> str:
        """
        Return a string representation of the FhirBundleEntryList.

        :return: A string representation of the FhirBundleEntryList.
        """
        return f"FhirBundleEntryList(entries: {len(self)})"

    @override
    def append(self, x: FhirBundleEntry, /) -> None:
        """
        Append an entry to the FhirBundleEntryList.

        :param x: The entry to append.
        """
        if not isinstance(x, FhirBundleEntry):
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
    def extend(self, iterable: Iterable[FhirBundleEntry], /) -> None:
        """
        Extend the FhirBundleEntryList with entries from an iterable.

        :param iterable: The iterable containing entries to extend.
        """
        for entry in iterable:
            self.append(entry)
