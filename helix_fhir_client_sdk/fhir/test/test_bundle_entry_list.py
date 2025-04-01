import pytest
from helix_fhir_client_sdk.fhir.fhir_bundle_entry import FhirBundleEntry
from helix_fhir_client_sdk.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)


@pytest.mark.asyncio
class TestFhirBundleEntryList:
    async def test_consume_resource_async_with_none_batch_size(self) -> None:
        """
        Test consuming bundle entries when batch_size is None.
        Each call should yield a single entry.
        """
        # Arrange
        entries = [
            FhirBundleEntry(
                resource={"id": "1"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirBundleEntry(
                resource={"id": "2"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirBundleEntry(
                resource={"id": "3"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
        ]
        bundle_list = FhirBundleEntryList(entries)

        # Act
        batches = []
        async for batch in bundle_list.consume_resource_async(batch_size=None):
            batches.append(batch)

        # Assert
        assert len(batches) == 3
        assert all(len(batch) == 1 for batch in batches)
        assert len(bundle_list) == 0  # All entries should be consumed

    @pytest.mark.parametrize("batch_size", [1, 2, 3, 5])
    async def test_consume_resource_async_with_valid_batch_sizes(
        self, batch_size: int
    ) -> None:
        """
        Test consuming bundle entries with various valid batch sizes.
        """
        # Arrange
        entries = [
            FhirBundleEntry(
                resource={"id": "1"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirBundleEntry(
                resource={"id": "2"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirBundleEntry(
                resource={"id": "3"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirBundleEntry(
                resource={"id": "4"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirBundleEntry(
                resource={"id": "5"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
        ]
        bundle_list = FhirBundleEntryList(entries)

        # Act
        batches = []
        async for batch in bundle_list.consume_resource_async(batch_size=batch_size):
            batches.append(batch)

        # Assert
        expected_batch_count = (len(entries) + batch_size - 1) // batch_size
        assert len(batches) == expected_batch_count
        assert all(len(batch) <= batch_size for batch in batches)
        assert sum(len(batch) for batch in batches) == len(entries)
        assert len(bundle_list) == 0  # All entries should be consumed

    async def test_consume_resource_async_with_zero_batch_size(self) -> None:
        """
        Test that consuming with batch_size <= 0 raises a ValueError.
        """
        # Arrange
        entries = [
            FhirBundleEntry(
                resource={"id": "1"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            )
        ]
        bundle_list = FhirBundleEntryList(entries)

        # Act & Assert
        with pytest.raises(ValueError, match="Batch size must be greater than 0."):
            async for _ in bundle_list.consume_resource_async(batch_size=0):
                pass

    async def test_consume_resource_async_with_empty_list(self) -> None:
        """
        Test consuming an empty list.
        """
        # Arrange
        bundle_list = FhirBundleEntryList()

        # Act
        batches = []
        async for batch in bundle_list.consume_resource_async(batch_size=2):
            batches.append(batch)

        # Assert
        assert len(batches) == 0

    def test_class_inheritance(self) -> None:
        """
        Verify that FhirBundleEntryList inherits from collections.deque
        and supports deque operations.
        """
        # Arrange
        entries = [
            FhirBundleEntry(
                resource={"id": "1"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
            FhirBundleEntry(
                resource={"id": "2"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            ),
        ]

        # Act
        bundle_list = FhirBundleEntryList(entries)

        # Assert
        assert len(bundle_list) == 2
        bundle_list.append(
            FhirBundleEntry(
                resource={"id": "3"},
                request=None,
                response=None,
                fullUrl=None,
                storage_mode=CompressedDictStorageMode(),
            )
        )
        assert len(bundle_list) == 3
        resource = bundle_list.popleft().resource
        assert resource is not None
        assert resource.to_dict() == {"id": "1"}
