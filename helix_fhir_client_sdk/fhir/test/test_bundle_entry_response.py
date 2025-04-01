from datetime import datetime, timezone

from helix_fhir_client_sdk.fhir.fhir_bundle_entry_response import (
    FhirBundleEntryResponse,
)


class TestBundleEntryResponse:
    def test_init_default(self) -> None:
        """Test initialization with default parameters."""
        response = FhirBundleEntryResponse(status="200", etag=None, lastModified=None)
        assert response.status == "200"
        assert response.etag is None
        assert response.lastModified is None

    def test_init_full(self) -> None:
        """Test initialization with all parameters."""
        now = datetime.now(timezone.utc)
        response = FhirBundleEntryResponse(
            status="201", etag='W/"def"', lastModified=now
        )
        assert response.status == "201"
        assert response.etag == 'W/"def"'
        assert response.lastModified == now

    def test_init_int_status(self) -> None:
        """Test initialization with integer status."""
        response = FhirBundleEntryResponse(status="200", etag=None, lastModified=None)
        assert response.status == "200"

    def test_to_dict_minimal(self) -> None:
        """Test converting to dictionary with minimal parameters."""
        response = FhirBundleEntryResponse(status="200", etag=None, lastModified=None)
        result = response.to_dict()
        assert result == {"status": "200"}

    def test_to_dict_full(self) -> None:
        """Test converting to dictionary with all parameters."""
        now = datetime.now(timezone.utc)
        response = FhirBundleEntryResponse(
            status="201", etag='W/"def"', lastModified=now
        )
        result = response.to_dict()
        assert result == {
            "status": "201",
            "lastModified": now.isoformat(),
            "etag": 'W/"def"',
        }

    def test_from_dict_minimal(self) -> None:
        """Test creating from dictionary with minimal parameters."""
        data = {"status": "200"}
        response = FhirBundleEntryResponse.from_dict(data)
        assert response.status == "200"
        assert response.etag is None
        assert response.lastModified is None

    def test_from_dict_full(self) -> None:
        """Test creating from dictionary with all parameters."""
        now = datetime.now(timezone.utc)
        data = {"status": "201", "lastModified": now.isoformat(), "etag": 'W/"def"'}
        response = FhirBundleEntryResponse.from_dict(data)
        assert response.status == "201"
        assert response.lastModified == now
        assert response.etag == 'W/"def"'
