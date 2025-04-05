import json
from unittest.mock import Mock

import pytest

from helix_fhir_client_sdk.fhir.fhir_resource_list import FhirResourceList


class TestFhirResourceList:
    def test_get_resource_type_and_ids(self) -> None:
        # Create mock FhirResource objects
        mock_resources = [
            Mock(resource_type="Patient", id="123"),
            Mock(resource_type="Observation", id="456"),
        ]

        resource_list = FhirResourceList(mock_resources)

        # Check the returned resource type and ids
        expected_result = ["Patient/123", "Observation/456"]
        assert resource_list.get_resource_type_and_ids() == expected_result

    def test_get_operation_outcomes(self) -> None:
        # Create mock FhirResource objects with different resource types
        mock_resources = [
            Mock(resource_type="OperationOutcome", id="err1"),
            Mock(resource_type="Patient", id="123"),
            Mock(resource_type="OperationOutcome", id="err2"),
        ]

        resource_list = FhirResourceList(mock_resources)

        # Get operation outcomes
        operation_outcomes = resource_list.get_operation_outcomes()

        # Check the result
        assert len(operation_outcomes) == 2
        assert all(r.resource_type == "OperationOutcome" for r in operation_outcomes)

    def test_get_resources_except_operation_outcomes(self) -> None:
        # Create mock FhirResource objects with different resource types
        mock_resources = [
            Mock(resource_type="OperationOutcome", id="err1"),
            Mock(resource_type="Patient", id="123"),
            Mock(resource_type="Observation", id="456"),
            Mock(resource_type="OperationOutcome", id="err2"),
        ]

        resource_list = FhirResourceList(mock_resources)

        # Get resources except operation outcomes
        valid_resources = resource_list.get_resources_except_operation_outcomes()

        # Check the result
        assert len(valid_resources) == 2
        assert all(r.resource_type != "OperationOutcome" for r in valid_resources)

    def test_remove_duplicates(self) -> None:
        # Create mock FhirResource objects with duplicates
        mock_resources = [
            Mock(resource_type="Patient", id="123", resource_type_and_id="Patient/123"),
            Mock(resource_type="Patient", id="123", resource_type_and_id="Patient/123"),
            Mock(
                resource_type="Observation",
                id="456",
                resource_type_and_id="Observation/456",
            ),
            Mock(resource_type="Patient", id="789", resource_type_and_id="Patient/789"),
        ]

        resource_list = FhirResourceList(mock_resources)

        # Remove duplicates
        resource_list.remove_duplicates()

        # Check the result
        assert len(resource_list) == 3
        assert len(set(r.resource_type_and_id for r in resource_list)) == 3

    def test_to_json(self) -> None:
        # Create mock FhirResource objects
        mock_resources = [
            Mock(
                resource_type="Patient",
                id="123",
                to_dict=lambda: {"id": "123", "resourceType": "Patient"},
            ),
            Mock(
                resource_type="Observation",
                id="456",
                to_dict=lambda: {"id": "456", "resourceType": "Observation"},
            ),
        ]

        resource_list = FhirResourceList(mock_resources)

        # Convert to JSON
        json_str = resource_list.to_json()

        # Parse and check the JSON
        parsed_json = json.loads(json_str)
        assert len(parsed_json) == 2
        assert parsed_json[0]["resourceType"] == "Patient"
        assert parsed_json[1]["resourceType"] == "Observation"

    @pytest.mark.asyncio
    async def test_consume_resource_async_default(self) -> None:
        # Create mock FhirResource objects
        mock_resources = [
            Mock(resource_type="Patient", id="123"),
            Mock(resource_type="Observation", id="456"),
        ]

        resource_list = FhirResourceList(mock_resources)

        # Consume resources asynchronously with default (None) batch size
        async for batch in resource_list.consume_resource_batch_async(batch_size=None):
            assert len(batch) == 1

        # Ensure all resources are consumed
        assert len(resource_list) == 0

    @pytest.mark.asyncio
    async def test_consume_resource_async_with_batch_size(self) -> None:
        # Create mock FhirResource objects
        mock_resources = [
            Mock(resource_type="Patient", id="123"),
            Mock(resource_type="Observation", id="456"),
            Mock(resource_type="Condition", id="789"),
        ]

        resource_list = FhirResourceList(mock_resources)

        # Consume resources asynchronously with batch size of 2
        batches = []
        async for batch in resource_list.consume_resource_batch_async(batch_size=2):
            batches.append(batch)

        # Check batches
        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

        # Ensure all resources are consumed
        assert len(resource_list) == 0

    def test_consume_resource_async_invalid_batch_size(self) -> None:
        resource_list = FhirResourceList()

        # Test invalid batch sizes
        with pytest.raises(ValueError, match="Batch size must be greater than 0."):

            async def test() -> None:
                async for _ in resource_list.consume_resource_batch_async(batch_size=0):
                    pass

            # Run the async function
            import asyncio

            asyncio.run(test())
