"""
Global pytest configuration for helix_fhir_client_sdk tests.

This module sets up test fixtures and ensures proper test isolation
for the singleton FhirClient pattern.
"""

import pytest
from helix_fhir_client_sdk.fhir_client import FhirClient


@pytest.fixture(autouse=True)
def reset_fhir_client_singleton():
    """
    Automatically reset the FhirClient singleton before each test.
    
    This fixture runs automatically before each test to ensure that tests
    don't interfere with each other when using the singleton FhirClient.
    """
    # Reset the singleton before the test
    FhirClient.reset_singleton()
    
    # Run the test
    yield
    
    # Optional: Reset again after the test for cleanup
    FhirClient.reset_singleton()


@pytest.fixture
def fhir_client() -> FhirClient:
    """
    Fixture to provide a fresh FhirClient instance for testing.
    
    Returns:
        FhirClient: A fresh FhirClient instance
    """
    return FhirClient()
