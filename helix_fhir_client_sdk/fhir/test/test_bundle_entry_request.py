from datetime import datetime, timezone

from helix_fhir_client_sdk.fhir.bundle_entry_request import BundleEntryRequest


class TestBundleEntryRequest:
    def test_init_default(self) -> None:
        """Test initialization with default parameters."""
        request = BundleEntryRequest(url="https://example.com")
        assert request.url == "https://example.com"
        assert request.method == "GET"
        assert request.ifModifiedSince is None
        assert request.ifNoneMatch is None

    def test_init_full(self) -> None:
        """Test initialization with all parameters."""
        now = datetime.now(timezone.utc)
        request = BundleEntryRequest(
            url="https://example.com",
            method="POST",
            ifModifiedSince=now,
            ifNoneMatch='W/"abc"',
        )
        assert request.url == "https://example.com"
        assert request.method == "POST"
        assert request.ifModifiedSince == now
        assert request.ifNoneMatch == 'W/"abc"'

    def test_to_dict_minimal(self) -> None:
        """Test converting to dictionary with minimal parameters."""
        request = BundleEntryRequest(url="https://example.com")
        result = request.to_dict()
        assert result == {"url": "https://example.com", "method": "GET"}

    def test_to_dict_full(self) -> None:
        """Test converting to dictionary with all parameters."""
        now = datetime.now(timezone.utc)
        request = BundleEntryRequest(
            url="https://example.com",
            method="POST",
            ifModifiedSince=now,
            ifNoneMatch='W/"abc"',
        )
        result = request.to_dict()
        assert result == {
            "url": "https://example.com",
            "method": "POST",
            "ifModifiedSince": now.isoformat(),
            "ifNoneMatch": 'W/"abc"',
        }

    def test_from_dict_minimal(self) -> None:
        """Test creating from dictionary with minimal parameters."""
        data = {"url": "https://example.com", "method": "GET"}
        request = BundleEntryRequest.from_dict(data)
        assert request.url == "https://example.com"
        assert request.method == "GET"
        assert request.ifModifiedSince is None
        assert request.ifNoneMatch is None

    def test_from_dict_full(self) -> None:
        """Test creating from dictionary with all parameters."""
        now = datetime.now(timezone.utc)
        data = {
            "url": "https://example.com",
            "method": "POST",
            "ifModifiedSince": now.isoformat(),
            "ifNoneMatch": 'W/"abc"',
        }
        request = BundleEntryRequest.from_dict(data)
        assert request.url == "https://example.com"
        assert request.method == "POST"
        assert request.ifModifiedSince == now
        assert request.ifNoneMatch == 'W/"abc"'
