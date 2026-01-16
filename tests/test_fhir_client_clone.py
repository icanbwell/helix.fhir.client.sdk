"""
Tests for FhirClient.clone() method to ensure all properties are properly copied.
"""

from datetime import UTC, datetime, timedelta

from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.fhir_client import FhirClient


def test_clone_preserves_compress_setting() -> None:
    """Test that clone() preserves the _compress setting"""
    # Create a client with compression disabled
    fhir_client = FhirClient().url("http://example.com").compress(False)
    assert fhir_client._compress is False

    # Clone and verify compression is still disabled
    cloned_client = fhir_client.clone()
    assert cloned_client._compress is False

    # Test with compression enabled
    fhir_client2 = FhirClient().url("http://example.com").compress(True)
    assert fhir_client2._compress is True

    cloned_client2 = fhir_client2.clone()
    assert cloned_client2._compress is True


def test_clone_preserves_storage_mode() -> None:
    """Test that clone() preserves the _storage_mode setting"""
    # Create a client with msgpack storage mode
    storage_mode = CompressedDictStorageMode(storage_type="msgpack")
    fhir_client = FhirClient().url("http://example.com").set_storage_mode(storage_mode)
    assert fhir_client._storage_mode.storage_type == "msgpack"

    # Clone and verify storage mode is preserved
    cloned_client = fhir_client.clone()
    assert cloned_client._storage_mode.storage_type == "msgpack"


def test_clone_preserves_additional_settings() -> None:
    """Test that clone() preserves other compression-related settings"""
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .compress(False)
        .send_data_as_chunked(True)
        .use_post_for_search(True)
        .maximum_time_to_retry_on_429(120)
        .retry_count(5)
        .throw_exception_on_error(False)
        .set_log_all_response_urls(True)
        .set_create_operation_outcome_for_error(True)
    )

    cloned_client = fhir_client.clone()

    assert cloned_client._compress is False
    assert cloned_client._send_data_as_chunked is True
    assert cloned_client._use_post_for_search is True
    assert cloned_client._maximum_time_to_retry_on_429 == 120
    assert cloned_client._retry_count == 5
    assert cloned_client._throw_exception_on_error is False
    assert cloned_client._log_all_response_urls is True
    assert cloned_client._create_operation_outcome_for_error is True


def test_default_compression_is_enabled() -> None:
    """Test that compression is enabled by default"""
    fhir_client = FhirClient()
    assert fhir_client._compress is True


def test_default_storage_mode_is_raw() -> None:
    """Test that the default storage mode is 'raw'"""
    fhir_client = FhirClient()
    assert fhir_client._storage_mode.storage_type == "raw"


def test_clone_preserves_access_token() -> None:
    """Test that clone() preserves access token and expiry date"""
    expiry_date = datetime.now(UTC) + timedelta(hours=1)
    fhir_client = (
        FhirClient()
        .url("http://example.com")
        .set_access_token("test-access-token-12345")
        .set_access_token_expiry_date(expiry_date)
    )

    assert fhir_client._access_token == "test-access-token-12345"
    assert fhir_client._access_token_expiry_date == expiry_date

    # Clone and verify access token is preserved
    cloned_client = fhir_client.clone()

    assert cloned_client._access_token == "test-access-token-12345"
    assert cloned_client._access_token_expiry_date == expiry_date


def test_clone_preserves_max_concurrent_requests() -> None:
    """Test that clone() preserves max_concurrent_requests setting"""
    fhir_client = FhirClient().url("http://example.com").set_max_concurrent_requests(10)

    assert fhir_client._max_concurrent_requests == 10

    # Clone and verify max_concurrent_requests is preserved
    cloned_client = fhir_client.clone()

    assert cloned_client._max_concurrent_requests == 10


def test_use_http_session() -> None:
    """Test that use_http_session sets the callable correctly"""
    from aiohttp import ClientSession

    def custom_session_factory() -> ClientSession:
        return ClientSession()

    fhir_client = FhirClient().url("http://example.com")

    # Initially None
    assert fhir_client._fn_create_http_session is None

    # Set the callable
    result = fhir_client.use_http_session(custom_session_factory)

    # Returns self for chaining
    assert result is fhir_client

    # Callable is stored
    assert fhir_client._fn_create_http_session is custom_session_factory

    # Can set to None
    fhir_client.use_http_session(None)
    assert fhir_client._fn_create_http_session is None


def test_clone_preserves_fn_create_http_session() -> None:
    """Test that clone() preserves the _fn_create_http_session callable"""
    from aiohttp import ClientSession

    def custom_session_factory() -> ClientSession:
        return ClientSession()

    fhir_client = FhirClient().url("http://example.com").use_http_session(custom_session_factory)

    assert fhir_client._fn_create_http_session is custom_session_factory

    # Clone and verify fn_create_http_session is preserved
    cloned_client = fhir_client.clone()

    assert cloned_client._fn_create_http_session is custom_session_factory
