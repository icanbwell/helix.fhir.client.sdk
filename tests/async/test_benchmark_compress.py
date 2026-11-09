"""
Benchmark tests for comparing compressed vs uncompressed FHIR client operations.

These tests measure the performance of:
- get_async() with compress=True vs compress=False
- get_raw_resources_async() with compress=True vs compress=False

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
   docker-compose run --rm dev pytest tests/async/test_benchmark_compress.py -v --benchmark-only

4. Or run all benchmark variations:
   docker-compose run --rm dev pytest tests/async/test_benchmark_compress.py -v --benchmark-only --benchmark-group-by=func

5. Save benchmark results for comparison:
   docker-compose run --rm dev pytest tests/async/test_benchmark_compress.py -v --benchmark-autosave

6. Compare with previous runs:
   docker-compose run --rm dev pytest tests/async/test_benchmark_compress.py -v --benchmark-compare

7. Run with more iterations for accuracy:
   docker-compose run --rm dev pytest tests/async/test_benchmark_compress.py -v --benchmark-min-rounds=10

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
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


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


# Skip all tests if mock-server is not running
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


def generate_patient_bundle(count: int) -> dict[str, Any]:
    """Generate a FHIR Bundle with multiple Patient resources."""
    entries = []
    for i in range(count):
        entries.append(
            {
                "fullUrl": f"http://example.org/fhir/Patient/patient-{i}",
                "resource": generate_patient_resource(i),
                "search": {"mode": "match"},
            }
        )
    return {
        "resourceType": "Bundle",
        "id": "bundle-search-result",
        "type": "searchset",
        "total": count,
        "link": [
            {"relation": "self", "url": f"http://example.org/fhir/Patient?_count={count}"},
        ],
        "entry": entries,
    }


@pytest.fixture(scope="module")
def mock_server_url() -> str:
    return "http://mock-server:1080"


@pytest.fixture(scope="module")
def mock_client(mock_server_url: str) -> MockServerFriendlyClient:
    return MockServerFriendlyClient(base_url=mock_server_url)


@pytest.fixture(scope="module")
def setup_mock_endpoints(mock_client: MockServerFriendlyClient, mock_server_url: str) -> str:
    """Set up mock endpoints for different payload sizes."""
    test_name = "benchmark_compress"

    mock_client.clear(f"/{test_name}/*.*")
    mock_client.reset()

    # Create payloads of different sizes for benchmarking
    payloads = {
        "small": generate_patient_bundle(10),  # ~10KB
        "medium": generate_patient_bundle(100),  # ~100KB
        "large": generate_patient_bundle(500),  # ~500KB
    }

    # Setup mock endpoints for each payload size
    for size, bundle in payloads.items():
        response_body = json.dumps(bundle)
        # Endpoint for GET /Patient (returns bundle)
        mock_client.expect(
            request=mock_request(path=f"/{test_name}/{size}/Patient", method="GET"),
            response=mock_response(body=response_body),
            timing=times(10000),  # Allow many requests for benchmarking
        )
        # Endpoint for GET /Patient/{id} (returns single resource)
        mock_client.expect(
            request=mock_request(path=f"/{test_name}/{size}/Patient/{size}", method="GET"),
            response=mock_response(body=response_body),
            timing=times(10000),
        )

    return f"{mock_server_url}/{test_name}"


# ============================================================================
# Benchmark Tests for get_async()
# ============================================================================


def test_benchmark_get_async_compress_false_small(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_async with compress=False and a small payload (10 patients)."""
    base_url = f"{setup_mock_endpoints}/small"

    async def run_get_async() -> FhirGetResponse:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(False).get_async()

    def run_sync() -> FhirGetResponse:
        return asyncio.run(run_get_async())

    result = benchmark(run_sync)
    assert result is not None
    assert result.get_response_text() is not None


def test_benchmark_get_async_compress_true_small(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_async with compress=True and a small payload (10 patients)."""
    base_url = f"{setup_mock_endpoints}/small"

    async def run_get_async() -> FhirGetResponse:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(True).get_async()

    def run_sync() -> FhirGetResponse:
        return asyncio.run(run_get_async())

    result = benchmark(run_sync)
    assert result is not None
    assert result.get_response_text() is not None


def test_benchmark_get_async_compress_false_medium(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_async with compress=False and medium payload (100 patients)."""
    base_url = f"{setup_mock_endpoints}/medium"

    async def run_get_async() -> FhirGetResponse:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(False).get_async()

    def run_sync() -> FhirGetResponse:
        return asyncio.run(run_get_async())

    result = benchmark(run_sync)
    assert result is not None
    assert result.get_response_text() is not None


def test_benchmark_get_async_compress_true_medium(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_async with compress=True and medium payload (100 patients)."""
    base_url = f"{setup_mock_endpoints}/medium"

    async def run_get_async() -> FhirGetResponse:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(True).get_async()

    def run_sync() -> FhirGetResponse:
        return asyncio.run(run_get_async())

    result = benchmark(run_sync)
    assert result is not None
    assert result.get_response_text() is not None


def test_benchmark_get_async_compress_false_large(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_async with compress=False and a large payload (500 patients)."""
    base_url = f"{setup_mock_endpoints}/large"

    async def run_get_async() -> FhirGetResponse:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(False).get_async()

    def run_sync() -> FhirGetResponse:
        return asyncio.run(run_get_async())

    result = benchmark(run_sync)
    assert result is not None
    assert result.get_response_text() is not None


def test_benchmark_get_async_compress_true_large(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_async with compress=True and a large payload (500 patients)."""
    base_url = f"{setup_mock_endpoints}/large"

    async def run_get_async() -> FhirGetResponse:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(True).get_async()

    def run_sync() -> FhirGetResponse:
        return asyncio.run(run_get_async())

    result = benchmark(run_sync)
    assert result is not None
    assert result.get_response_text() is not None


# ============================================================================
# Benchmark Tests for get_raw_resources_async()
# ============================================================================


def test_benchmark_get_raw_resources_async_compress_false_small(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_raw_resources_async with compress=False and small payload."""
    base_url = f"{setup_mock_endpoints}/small"

    async def run_get_raw() -> dict[str, Any]:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(False).get_raw_resources_async()

    def run_sync() -> dict[str, Any]:
        return asyncio.run(run_get_raw())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_get_raw_resources_async_compress_true_small(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_raw_resources_async with compress=True and a small payload."""
    base_url = f"{setup_mock_endpoints}/small"

    async def run_get_raw() -> dict[str, Any]:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(True).get_raw_resources_async()

    def run_sync() -> dict[str, Any]:
        return asyncio.run(run_get_raw())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_get_raw_resources_async_compress_false_medium(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_raw_resources_async with compress=False and medium payload."""
    base_url = f"{setup_mock_endpoints}/medium"

    async def run_get_raw() -> dict[str, Any]:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(False).get_raw_resources_async()

    def run_sync() -> dict[str, Any]:
        return asyncio.run(run_get_raw())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_get_raw_resources_async_compress_true_medium(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_raw_resources_async with compress=True and medium payload."""
    base_url = f"{setup_mock_endpoints}/medium"

    async def run_get_raw() -> dict[str, Any]:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(True).get_raw_resources_async()

    def run_sync() -> dict[str, Any]:
        return asyncio.run(run_get_raw())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_get_raw_resources_async_compress_false_large(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_raw_resources_async with compress=False and a large payload."""
    base_url = f"{setup_mock_endpoints}/large"

    async def run_get_raw() -> dict[str, Any]:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(False).get_raw_resources_async()

    def run_sync() -> dict[str, Any]:
        return asyncio.run(run_get_raw())

    result = benchmark(run_sync)
    assert result is not None


def test_benchmark_get_raw_resources_async_compress_true_large(benchmark: Any, setup_mock_endpoints: str) -> None:
    """Benchmark get_raw_resources_async with compress=True and a large payload."""
    base_url = f"{setup_mock_endpoints}/large"

    async def run_get_raw() -> dict[str, Any]:
        fhir_client = FhirClient().url(base_url).resource("Patient")
        return await fhir_client.compress(True).get_raw_resources_async()

    def run_sync() -> dict[str, Any]:
        return asyncio.run(run_get_raw())

    result = benchmark(run_sync)
    assert result is not None
