import json
from datetime import datetime, timezone

from helix_fhir_client_sdk.fhir_bundle import (
    Bundle,
    BundleEntry,
    BundleEntryRequest,
    BundleEntryResponse,
)


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


class TestBundleEntryResponse:
    def test_init_default(self) -> None:
        """Test initialization with default parameters."""
        response = BundleEntryResponse(status="200", etag=None, lastModified=None)
        assert response.status == "200"
        assert response.etag is None
        assert response.lastModified is None

    def test_init_full(self) -> None:
        """Test initialization with all parameters."""
        now = datetime.now(timezone.utc)
        response = BundleEntryResponse(status="201", etag='W/"def"', lastModified=now)
        assert response.status == "201"
        assert response.etag == 'W/"def"'
        assert response.lastModified == now

    def test_init_int_status(self) -> None:
        """Test initialization with integer status."""
        response = BundleEntryResponse(status="200", etag=None, lastModified=None)
        assert response.status == "200"

    def test_to_dict_minimal(self) -> None:
        """Test converting to dictionary with minimal parameters."""
        response = BundleEntryResponse(status="200", etag=None, lastModified=None)
        result = response.to_dict()
        assert result == {"status": "200"}

    def test_to_dict_full(self) -> None:
        """Test converting to dictionary with all parameters."""
        now = datetime.now(timezone.utc)
        response = BundleEntryResponse(status="201", etag='W/"def"', lastModified=now)
        result = response.to_dict()
        assert result == {
            "status": "201",
            "lastModified": now.isoformat(),
            "etag": 'W/"def"',
        }

    def test_from_dict_minimal(self) -> None:
        """Test creating from dictionary with minimal parameters."""
        data = {"status": "200"}
        response = BundleEntryResponse.from_dict(data)
        assert response.status == "200"
        assert response.etag is None
        assert response.lastModified is None

    def test_from_dict_full(self) -> None:
        """Test creating from dictionary with all parameters."""
        now = datetime.now(timezone.utc)
        data = {"status": "201", "lastModified": now.isoformat(), "etag": 'W/"def"'}
        response = BundleEntryResponse.from_dict(data)
        assert response.status == "201"
        assert response.lastModified == now
        assert response.etag == 'W/"def"'


class TestBundleEntry:
    def test_init_minimal(self) -> None:
        """Test initialization with minimal parameters."""
        entry = BundleEntry(
            resource={"resourceType": "Patient"}, request=None, response=None
        )
        assert entry.resource == {"resourceType": "Patient"}
        assert entry.request is None
        assert entry.response is None
        assert entry.fullUrl is None

    def test_init_full(self) -> None:
        """Test initialization with all parameters."""
        resource = {"resourceType": "Patient", "id": "123"}
        request = BundleEntryRequest(url="https://example.com")
        response = BundleEntryResponse(status="200", etag=None, lastModified=None)

        entry = BundleEntry(
            resource=resource,
            request=request,
            response=response,
            fullUrl="https://example.com/Patient/123",
        )
        assert entry.resource == resource
        assert entry.request == request
        assert entry.response == response
        assert entry.fullUrl == "https://example.com/Patient/123"

    def test_to_dict_minimal(self) -> None:
        """Test converting to dictionary with minimal parameters."""
        entry = BundleEntry(
            resource={"resourceType": "Patient"}, request=None, response=None
        )
        result = entry.to_dict()
        assert result == {"resource": {"resourceType": "Patient"}}

    def test_to_dict_full(self) -> None:
        """Test converting to dictionary with all parameters."""
        resource = {"resourceType": "Patient", "id": "123"}
        request = BundleEntryRequest(url="https://example.com")
        response = BundleEntryResponse(status="200", etag=None, lastModified=None)

        entry = BundleEntry(
            resource=resource,
            request=request,
            response=response,
            fullUrl="https://example.com/Patient/123",
        )
        result = entry.to_dict()
        assert result == {
            "fullUrl": "https://example.com/Patient/123",
            "resource": resource,
            "request": request.to_dict(),
            "response": response.to_dict(),
        }

    def test_from_dict_minimal(self) -> None:
        """Test creating from dictionary with minimal parameters."""
        data = {"resource": {"resourceType": "Patient"}}
        entry = BundleEntry.from_dict(data)
        assert entry.resource == {"resourceType": "Patient"}
        assert entry.request is None
        assert entry.response is None
        assert entry.fullUrl is None

    def test_from_dict_full(self) -> None:
        """Test creating from dictionary with all parameters."""
        now = datetime.now(timezone.utc)
        data = {
            "fullUrl": "https://example.com/Patient/123",
            "resource": {"resourceType": "Patient", "id": "123"},
            "request": {"url": "https://example.com", "method": "GET"},
            "response": {
                "status": "200",
                "lastModified": now.isoformat(),
                "etag": 'W/"abc"',
            },
        }
        entry = BundleEntry.from_dict(data)
        assert entry.fullUrl == "https://example.com/Patient/123"
        assert entry.resource == {"resourceType": "Patient", "id": "123"}
        assert entry.request is not None
        assert entry.request.url == "https://example.com"
        assert entry.response is not None
        assert entry.response.status == "200"

    def test_repr(self) -> None:
        """Test string representation of BundleEntry."""
        resource = {"resourceType": "Patient", "id": "123"}
        entry = BundleEntry(resource=resource, request=None, response=None)
        assert repr(entry) == "resource={'resourceType': 'Patient', 'id': '123'}, "


class TestBundle:
    def test_init_minimal(self) -> None:
        """Test initialization with minimal parameters."""
        bundle = Bundle(type_="searchset")
        assert bundle.type_ == "searchset"
        assert bundle.entry is None
        assert bundle.total is None
        assert bundle.id_ is None
        assert bundle.timestamp is None

    def test_init_full(self) -> None:
        """Test initialization with all parameters."""
        entries = [
            BundleEntry(
                resource={"resourceType": "Patient"}, request=None, response=None
            ),
            BundleEntry(
                resource={"resourceType": "Observation"}, request=None, response=None
            ),
        ]
        bundle = Bundle(
            type_="searchset",
            entry=entries,
            total=2,
            id_="test-bundle",
            timestamp="2023-12-01T12:00:00Z",
        )
        assert bundle.type_ == "searchset"
        assert bundle.entry is not None
        assert len(bundle.entry) == 2
        assert bundle.total == 2
        assert bundle.id_ == "test-bundle"
        assert bundle.timestamp == "2023-12-01T12:00:00Z"

    def test_to_dict_minimal(self) -> None:
        """Test converting to dictionary with minimal parameters."""
        bundle = Bundle(type_="searchset")
        result = bundle.to_dict()
        assert result == {"type": "searchset", "resourceType": "Bundle"}

    def test_to_dict_full(self) -> None:
        """Test converting to dictionary with all parameters."""
        entries = [
            BundleEntry(
                resource={"resourceType": "Patient"}, request=None, response=None
            ),
            BundleEntry(
                resource={"resourceType": "Observation"}, request=None, response=None
            ),
        ]
        bundle = Bundle(
            type_="searchset",
            entry=entries,
            total=2,
            id_="test-bundle",
            timestamp="2023-12-01T12:00:00Z",
        )
        result = bundle.to_dict()
        assert result == {
            "type": "searchset",
            "resourceType": "Bundle",
            "id": "test-bundle",
            "timestamp": "2023-12-01T12:00:00Z",
            "total": 2,
            "entry": [
                {"resource": {"resourceType": "Patient"}},
                {"resource": {"resourceType": "Observation"}},
            ],
        }

    def test_to_json(self) -> None:
        """Test converting Bundle to JSON."""
        entries = [
            BundleEntry(
                resource={"resourceType": "Patient"}, request=None, response=None
            ),
            BundleEntry(
                resource={"resourceType": "Observation"}, request=None, response=None
            ),
        ]
        bundle = Bundle(
            type_="searchset",
            entry=entries,
            total=2,
            id_="test-bundle",
            timestamp="2023-12-01T12:00:00Z",
        )
        json_str = bundle.to_json()
        parsed_json = json.loads(json_str)
        assert parsed_json["type"] == "searchset"
        assert parsed_json["resourceType"] == "Bundle"

    def test_add_diagnostics_to_operation_outcomes(self) -> None:
        """Test adding diagnostics to OperationOutcome resources."""
        resource = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "details": {}}],
        }
        diagnostics_coding = [{"code": "test-code"}]

        updated_resource = Bundle.add_diagnostics_to_operation_outcomes(
            resource=resource, diagnostics_coding=diagnostics_coding
        )

        assert updated_resource["issue"][0]["details"]["coding"] == diagnostics_coding
