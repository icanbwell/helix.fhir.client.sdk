from datetime import UTC, datetime, timedelta

import pytest
from aioresponses import aioresponses

from helix_fhir_client_sdk.fhir_auth_mixin import FhirAuthMixin
from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.function_types import RefreshTokenResult
from helix_fhir_client_sdk.structures.get_access_token_result import (
    GetAccessTokenResult,
)
from helix_fhir_client_sdk.well_known_configuration import (
    WellKnownConfigurationCacheEntry,
)


@pytest.fixture
def fhir_auth_mixin() -> FhirAuthMixin:
    """Fixture to create an instance of FhirAuthMixin."""
    return FhirClient()


@pytest.mark.asyncio
async def test_get_auth_url_async_from_cache(fhir_auth_mixin: FhirAuthMixin) -> None:
    """Test getting the auth URL from the cache."""
    fhir_auth_mixin._well_known_configuration_cache = {
        "test_host": WellKnownConfigurationCacheEntry(
            auth_url="https://auth.test/token",
            last_updated_utc=datetime.now(UTC) - timedelta(seconds=300),
        )
    }
    fhir_auth_mixin._auth_wellknown_url = "https://test_host/.well-known/openid-configuration"

    auth_url = await fhir_auth_mixin.get_auth_url_async()
    assert auth_url == "https://auth.test/token"


@pytest.mark.asyncio
async def test_get_auth_url_async_from_well_known_configuration(
    fhir_auth_mixin: FhirAuthMixin,
) -> None:
    """Test getting the auth URL from the well-known configuration."""
    fhir_auth_mixin._auth_wellknown_url = "https://auth.test/.well-known/openid-configuration"

    with aioresponses() as m:
        m.get(
            "https://auth.test/.well-known/openid-configuration",
            payload={"token_endpoint": "https://auth.test/token"},
        )

        auth_url = await fhir_auth_mixin.get_auth_url_async()
        assert auth_url == "https://auth.test/token"
        assert fhir_auth_mixin._well_known_configuration_cache["auth.test"].auth_url == "https://auth.test/token"


@pytest.mark.asyncio
async def test_get_access_token_async(fhir_auth_mixin: FhirAuthMixin) -> None:
    # noinspection PyUnusedLocal
    async def refresh_token_function(
        url: str | None,
        status_code: int | None,
        current_token: str | None,
        expiry_date: datetime | None,
        retry_count: int | None,
    ) -> RefreshTokenResult:
        return RefreshTokenResult(access_token="test_access_token", expiry_date=None, abort_request=False)

    """Test getting the access token."""
    fhir_auth_mixin._refresh_token_function = refresh_token_function

    access_token_result: GetAccessTokenResult = await fhir_auth_mixin.get_access_token_async()
    access_token: str | None = access_token_result.access_token

    assert access_token == "test_access_token"
    assert fhir_auth_mixin._access_token == "test_access_token"


@pytest.mark.asyncio
async def test_authenticate_async(fhir_auth_mixin: FhirAuthMixin) -> None:
    """Test authenticating and getting an access token."""
    fhir_auth_mixin._auth_server_url = "https://auth.test/token"
    fhir_auth_mixin._login_token = "test_login_token"
    fhir_auth_mixin._auth_scopes = ["scope1", "scope2"]

    with aioresponses() as m:
        m.post("https://auth.test/token", payload={"access_token": "test_access_token"})

        refresh_token_result: RefreshTokenResult = await fhir_auth_mixin.authenticate_async()
        assert refresh_token_result.access_token == "test_access_token"


@pytest.mark.asyncio
async def test_authenticate_async_no_token(fhir_auth_mixin: FhirAuthMixin) -> None:
    """Test authenticating when no access token is returned."""
    fhir_auth_mixin._auth_server_url = "https://auth.test/token"
    fhir_auth_mixin._login_token = "test_login_token"
    fhir_auth_mixin._auth_scopes = ["scope1", "scope2"]

    with aioresponses() as m:
        m.post("https://auth.test/token", payload={})

        with pytest.raises(Exception, match="No access token found"):
            await fhir_auth_mixin.authenticate_async()


@pytest.mark.asyncio
async def test_create_login_token() -> None:
    """Test creating a login token."""
    client_id = "test_client_id"
    client_secret = "test_client_secret"  # pragma: allowlist secret
    expected_token = "dGVzdF9jbGllbnRfaWQ6dGVzdF9jbGllbnRfc2VjcmV0"

    token = FhirAuthMixin._create_login_token(client_id, client_secret)
    assert token == expected_token
