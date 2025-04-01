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
