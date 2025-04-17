# test_async_fhir_validator.py
import aiohttp
import pytest
from aiohttp import ClientSession
from aioresponses import aioresponses

from helix_fhir_client_sdk.exceptions.fhir_validation_exception import (
    FhirValidationException,
)
from helix_fhir_client_sdk.validators.async_fhir_validator import AsyncFhirValidator


@pytest.mark.asyncio
async def test_validate_fhir_resource_success() -> None:
    async def mock_get_session() -> ClientSession:
        return ClientSession()

    json_data = '{"resourceType": "Patient"}'
    resource_name = "Patient"
    validation_server_url = "http://validation-server.com"
    access_token = "test-token"

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                "http://validation-server.com/Patient/$validate",
                status=200,
                payload={"issue": []},
                headers={"X-Request-ID": "test-request-id"},
            )

            await AsyncFhirValidator.validate_fhir_resource(
                fn_get_session=lambda: session,
                json_data=json_data,
                resource_name=resource_name,
                validation_server_url=validation_server_url,
                access_token=access_token,
            )


@pytest.mark.asyncio
async def test_validate_fhir_resource_validation_error() -> None:
    json_data = '{"resourceType": "Patient"}'
    resource_name = "Patient"
    validation_server_url = "http://validation-server.com"
    access_token = "test-token"

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                "http://validation-server.com/Patient/$validate",
                status=200,
                payload={"issue": [{"severity": "error", "details": "Validation error"}]},
                headers={"X-Request-ID": "test-request-id"},
            )

            with pytest.raises(FhirValidationException):
                await AsyncFhirValidator.validate_fhir_resource(
                    fn_get_session=lambda: session,
                    json_data=json_data,
                    resource_name=resource_name,
                    validation_server_url=validation_server_url,
                    access_token=access_token,
                )


@pytest.mark.asyncio
async def test_validate_fhir_resource_server_error() -> None:
    json_data = '{"resourceType": "Patient"}'
    resource_name = "Patient"
    validation_server_url = "http://validation-server.com"
    access_token = "test-token"

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                "http://validation-server.com/Patient/$validate",
                status=500,
                body="Internal Server Error",
                headers={"X-Request-ID": "test-request-id"},
            )

            with pytest.raises(aiohttp.client_exceptions.ClientConnectionError):
                await AsyncFhirValidator.validate_fhir_resource(
                    fn_get_session=lambda: session,
                    json_data=json_data,
                    resource_name=resource_name,
                    validation_server_url=validation_server_url,
                    access_token=access_token,
                )
