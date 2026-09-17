"""
Tests for the connection pool configuration of FhirClient.create_http_session().
"""

from collections.abc import Callable

import aiohttp
import pytest
from aiohttp import ClientSession

from helix_fhir_client_sdk.fhir_client import FhirClient


def _connector_of(session: aiohttp.ClientSession) -> aiohttp.TCPConnector:
    """Narrows a session's connector to TCPConnector so its limits can be asserted on."""
    connector = session.connector
    assert isinstance(connector, aiohttp.TCPConnector)
    return connector


async def test_create_http_session_defaults_to_aiohttp_connection_limit() -> None:
    """Called with no arguments, as the SDK does internally, the pool matches aiohttp's default."""
    # Arrange
    fhir_client = FhirClient().url("http://example.com")

    # Act
    session = fhir_client.create_http_session()

    # Assert
    try:
        assert _connector_of(session).limit == 100
        # limit_per_host stays at aiohttp's unlimited default (0) so it never becomes the
        # binding cap ahead of the total limit.
        assert _connector_of(session).limit_per_host == 0
    finally:
        await session.close()


@pytest.mark.parametrize("connection_limit", [0, 1, 250, 500, 5000])
async def test_create_http_session_applies_requested_connection_limit(connection_limit: int) -> None:
    """The requested limit reaches the connector of the session that gets built."""
    # Arrange
    fhir_client = FhirClient().url("http://example.com")

    # Act
    session = fhir_client.create_http_session(connection_limit=connection_limit)

    # Assert
    try:
        assert _connector_of(session).limit == connection_limit
    finally:
        await session.close()


@pytest.mark.parametrize("connection_limit", [-1, -100])
def test_create_http_session_rejects_negative_connection_limit(connection_limit: int) -> None:
    """Negative limits are rejected at the call site rather than surfacing later from aiohttp."""
    # Arrange
    fhir_client = FhirClient().url("http://example.com")

    # Act / Assert
    with pytest.raises(ValueError, match="connection_limit must be 0"):
        fhir_client.create_http_session(connection_limit=connection_limit)


async def test_create_http_session_stays_usable_as_zero_argument_session_factory() -> None:
    """
    The SDK passes create_http_session as a zero-argument callable to RetryableAioHttpClient,
    so connection_limit must remain optional.
    """
    # Arrange
    fhir_client = FhirClient().url("http://example.com")
    fn_get_session: Callable[[], ClientSession] = fhir_client.create_http_session

    # Act
    session = fn_get_session()

    # Assert
    try:
        assert _connector_of(session).limit == 100
    finally:
        await session.close()


async def test_create_http_session_supports_shared_session_with_raised_limit() -> None:
    """A caller can build a raised-limit session and hand it back for reuse across requests."""
    # Arrange
    fhir_client = FhirClient().url("http://example.com")
    session = fhir_client.create_http_session(connection_limit=500)

    # Act
    fhir_client.use_http_session(lambda: session)

    # Assert
    try:
        assert fhir_client._fn_create_http_session is not None
        assert _connector_of(fhir_client._fn_create_http_session()).limit == 500
    finally:
        await session.close()
