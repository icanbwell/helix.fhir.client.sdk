from typing import Deque, Optional, AsyncGenerator, List

from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry


class FhirBundleEntryList(Deque[FhirBundleEntry]):
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

    def copy(self) -> "FhirBundleEntryList":
        """
        Create a shallow copy of the FhirBundleEntryList.

        :return: A new FhirBundleEntryList instance with the same entries.
        """
        return FhirBundleEntryList([entry.copy() for entry in self])

    def __repr__(self) -> str:
        """
        Return a string representation of the FhirBundleEntryList.

        :return: A string representation of the FhirBundleEntryList.
        """
        return f"FhirBundleEntryList(entries: {len(self)})"
