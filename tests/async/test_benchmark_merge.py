"""
Benchmark tests for comparing compressed vs uncompressed FHIR client merge operations.

These tests measure the performance of:
- merge_async() with compress=True vs compress=False

=============================================================================
HOW TO RUN THESE TESTS
=============================================================================

1. Start services using docker-compose:
   docker-compose up -d mock-server

2. First time only - rebuild dev container to include pytest-benchmark:
   docker-compose build dev

   OR install pytest-benchmark in the running container:
   docker-compose run --rm dev pip install pytest-benchmark

3. Run benchmark tests inside docker container:
   docker-compose run --rm dev pytest tests/async/test_benchmark_merge.py -v --benchmark-only

4. Or run all benchmark variations:
   docker-compose run --rm dev pytest tests/async/test_benchmark_merge.py -v --benchmark-only --benchmark-group-by=func

5. Save benchmark results for comparison:
   docker-compose run --rm dev pytest tests/async/test_benchmark_merge.py -v --benchmark-autosave

6. Compare with previous runs:
   docker-compose run --rm dev pytest tests/async/test_benchmark_merge.py -v --benchmark-compare

7. Run with more iterations for accuracy:
   docker-compose run --rm dev pytest tests/async/test_benchmark_merge.py -v --benchmark-min-rounds=10

8. To stop mock-server:
   docker-compose down mock-server

=============================================================================
"""

import asyncio
import json
import socket
from typing import Any

import pytest
from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse


def is_mock_server_running(host: str = "mock-server", port: int = 1080) -> bool:
    """Check if mock-server is reachable."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except OSError:
        return False


# Skip all tests if the mock-server is not running
pytestmark = pytest.mark.skipif(
    not is_mock_server_running(), reason="Mock server not running. Start with: docker-compose up -d mock-server"
)


def generate_patient_resource(index: int) -> dict[str, Any]:
    """Generate a realistic FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": f"patient-{index}",
        "meta": {
            "versionId": "1",
            "lastUpdated": "2025-01-15T10:30:00.000Z",
            "source": "http://example.org/fhir",
            "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"],
        },
        "identifier": [
            {
                "use": "official",
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "MR",
                            "display": "Medical Record Number",
                        }
                    ]
                },
                "system": "http://hospital.example.org/mrn",
                "value": f"MRN-{index:08d}",
            },
            {
                "use": "official",
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "SS",
                            "display": "Social Security Number",
                        }
                    ]
                },
                "system": "http://hl7.org/fhir/sid/us-ssn",
                "value": f"{100 + index:03d}-{50 + index:02d}-{1000 + index:04d}",
            },
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": f"TestFamily{index}",
                "given": [f"TestGiven{index}", f"MiddleName{index}"],
                "prefix": ["Mr."],
                "suffix": ["Jr."],
            },
            {
                "use": "nickname",
                "given": [f"Nick{index}"],
            },
        ],
        "telecom": [
            {"system": "phone", "value": f"555-{100 + index:03d}-{1000 + index:04d}", "use": "home"},
            {"system": "phone", "value": f"555-{200 + index:03d}-{2000 + index:04d}", "use": "mobile"},
            {"system": "email", "value": f"patient{index}@example.com", "use": "home"},
        ],
        "gender": "male" if index % 2 == 0 else "female",
        "birthDate": f"{1950 + (index % 50)}-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        "deceasedBoolean": False,
        "address": [
            {
                "use": "home",
                "type": "physical",
                "line": [f"{100 + index} Main Street", f"Apt {index}"],
                "city": "Boston",
                "state": "MA",
                "postalCode": f"02{100 + (index % 900):03d}",
                "country": "USA",
            },
            {
                "use": "work",
                "type": "postal",
                "line": [f"{200 + index} Business Ave"],
                "city": "Cambridge",
                "state": "MA",
                "postalCode": f"02{200 + (index % 800):03d}",
                "country": "USA",
            },
        ],
        "maritalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",
                    "code": "M" if index % 2 == 0 else "S",
                    "display": "Married" if index % 2 == 0 else "Never Married",
                }
            ]
        },
        "communication": [
            {
                "language": {
                    "coding": [
                        {
                            "system": "urn:ietf:bcp:47",
                            "code": "en-US",
                            "display": "English (United States)",
                        }
                    ]
                },
                "preferred": True,
            }
        ],
        "generalPractitioner": [{"reference": f"Practitioner/practitioner-{index % 10}"}],
        "managingOrganization": {"reference": "Organization/org-1"},
    }


def generate_patient_resources_list(count: int) -> list[dict[str, Any]]:
    """Generate a list of FHIR Patient resources."""
    return [generate_patient_resource(i) for i in range(count)]


def generate_merge_response(count: int) -> list[dict[str, Any]]:
    """Generate a merge response for the given count of resources."""
    return [{"created": 1, "updated": 0} for _ in range(count)]


@pytest.fixture(scope="module")
def mock_server_url() -> str:
    return "http://mock-server:1080"


@pytest.fixture(scope="module")
def mock_client(mock_server_url: str) -> MockServerFriendlyClient:
    return MockServerFriendlyClient(base_url=mock_server_url)


@pytest.fixture(scope="module")
def setup_mock_merge_endpoints(mock_client: MockServerFriendlyClient, mock_server_url: str) -> str:
    """Set up mock endpoints for merge operations with different payload sizes."""
    test_name = "benchmark_merge"

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    # Create payloads of different sizes for benchmarking
    payload_sizes = {
        "small": 10,  # 10 patients
        "medium": 100,  # 100 patients
        "large": 500,  # 500 patients
    }

    # Setup mock endpoints for each payload size - using regex to match any request body
    for size, count in payload_sizes.items():
        response_body = json.dumps(generate_merge_response(count))

        # Endpoint for POST /Patient/1/$merge (single resource merge)
        mock_client.expect(
            request=mock_request(
                path=f"/{test_name}/{size}/Patient/1/$merge",
                method="POST",
            ),
            response=mock_response(body=response_body),
            timing=times(10000),  # Allow many requests for benchmarking
        )

        # Endpoint for POST /Patient/$merge (batch merge)
        mock_client.expect(
            request=mock_request(
                path=f"/{test_name}/{size}/Patient/$merge",
                method="POST",
            ),
            response=mock_response(body=response_body),
            timing=times(10000),
        )

    return f"{mock_server_url}/{test_name}"


# ============================================================================
# Benchmark Tests for merge_async() - Small Payload (10 patients)
# ============================================================================


def test_benchmark_merge_async_compress_false_small(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark merge_async with compress=False and small payload (10 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/small"
    resources = generate_patient_resources_list(10)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(False)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(id_="1", json_data_list=json_data_list)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_merge_async_compress_true_small(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark merge_async with compress=True and small payload (10 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/small"
    resources = generate_patient_resources_list(10)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(True)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(id_="1", json_data_list=json_data_list)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


# ============================================================================
# Benchmark Tests for merge_async() - Medium Payload (100 patients)
# ============================================================================


def test_benchmark_merge_async_compress_false_medium(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark merge_async with compress=False and medium payload (100 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/medium"
    resources = generate_patient_resources_list(100)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(False)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(id_="1", json_data_list=json_data_list)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_merge_async_compress_true_medium(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark merge_async with compress=True and medium payload (100 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/medium"
    resources = generate_patient_resources_list(100)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(True)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(id_="1", json_data_list=json_data_list)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


# ============================================================================
# Benchmark Tests for merge_async() - Large Payload (500 patients)
# ============================================================================


def test_benchmark_merge_async_compress_false_large(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark merge_async with compress=False and large payload (500 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/large"
    resources = generate_patient_resources_list(500)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(False)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(id_="1", json_data_list=json_data_list)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_merge_async_compress_true_large(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark merge_async with compress=True and large payload (500 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/large"
    resources = generate_patient_resources_list(500)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(True)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(id_="1", json_data_list=json_data_list)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


# ============================================================================
# Benchmark Tests for batch merge_async() - Multiple resources in single call
# ============================================================================


def test_benchmark_batch_merge_async_compress_false_small(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark batch merge_async with compress=False and small payload (10 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/small"
    resources = generate_patient_resources_list(10)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(False)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=json_data_list, batch_size=10)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_batch_merge_async_compress_true_small(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark batch merge_async with compress=True and small payload (10 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/small"
    resources = generate_patient_resources_list(10)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(True)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=json_data_list, batch_size=10)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_batch_merge_async_compress_false_medium(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark batch merge_async with compress=False and medium payload (100 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/medium"
    resources = generate_patient_resources_list(100)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(False)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=json_data_list, batch_size=50)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_batch_merge_async_compress_true_medium(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark batch merge_async with compress=True and medium payload (100 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/medium"
    resources = generate_patient_resources_list(100)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(True)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=json_data_list, batch_size=50)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_batch_merge_async_compress_false_large(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark batch merge_async with compress=False and large payload (500 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/large"
    resources = generate_patient_resources_list(500)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(False)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=json_data_list, batch_size=100)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_batch_merge_async_compress_true_large(benchmark: Any, setup_mock_merge_endpoints: str) -> None:
    """Benchmark batch merge_async with compress=True and large payload (500 patients)."""
    base_url = f"{setup_mock_merge_endpoints}/large"
    resources = generate_patient_resources_list(500)
    json_data_list = [json.dumps(r) for r in resources]

    async def run_merge_async() -> FhirMergeResponse | None:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        fhir_client = fhir_client.compress(True)
        return await FhirMergeResponse.from_async_generator(
            fhir_client.merge_async(json_data_list=json_data_list, batch_size=100)
        )

    def run_sync() -> FhirMergeResponse | None:
        return asyncio.run(run_merge_async())

    result = benchmark(run_sync)
    assert result is not None
