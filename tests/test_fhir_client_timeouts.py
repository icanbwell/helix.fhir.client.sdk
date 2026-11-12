import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient


@pytest.mark.parametrize(
    "client_read_timeout,expected_sock_read",
    [(None, 240), (30, 30), (0.5, 0.5)],
    ids=["default", "read-timeout-set", "sub-second-read-timeout"],
)
@pytest.mark.asyncio
async def test_create_http_session_uses_read_timeout(
    client_read_timeout: float | None, expected_sock_read: float
) -> None:
    # Arrange
    fhir_client = FhirClient()
    if client_read_timeout is not None:
        fhir_client = fhir_client.read_timeout(client_read_timeout)

    # Act
    session = fhir_client.create_http_session()

    # Assert
    try:
        assert session.timeout.sock_read == expected_sock_read
        assert session.timeout.total == 60 * 60
    finally:
        await session.close()


@pytest.mark.parametrize(
    "configure",
    [
        lambda c: c.read_timeout(0),
        lambda c: c.read_timeout(-5),
        lambda c: c.timeout_retry_count(-1),
    ],
    ids=["zero-read-timeout", "negative-read-timeout", "negative-timeout-retries"],
)
def test_invalid_timeout_settings_are_rejected(configure: object) -> None:
    with pytest.raises(ValueError):
        configure(FhirClient())  # type: ignore[operator]


def test_clone_keeps_timeout_settings() -> None:
    # Arrange
    fhir_client = FhirClient().read_timeout(30).timeout_retry_count(0)

    # Act
    cloned = fhir_client.clone()

    # Assert
    assert cloned._read_timeout_seconds == 30
    assert cloned._timeout_retry_count == 0
