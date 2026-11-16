"""FhirGetResponse.lastModified and etag are parsed once and reused until response_headers changes.
All data is synthetic."""

import json
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from dateutil import parser

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.responses.get.fhir_get_response_factory import (
    FhirGetResponseFactory,
)


def _response(headers: list[str] | None, body: Any = None) -> FhirGetResponse:
    return FhirGetResponseFactory.create(
        request_id=None,
        url="https://example.com/fhir/Patient",
        response_text=json.dumps(body if body is not None else {"resourceType": "Patient", "id": "p1"}),
        error=None,
        access_token=None,
        total_count=1,
        status=200,
        extra_context_to_return=None,
        resource_type="Patient",
        id_=None,
        response_headers=headers,
        results_by_url=[],
        storage_mode=CompressedDictStorageMode.raw(),
        create_operation_outcome_for_error=False,
    )


@pytest.mark.parametrize(
    ("headers", "expected_last_modified", "expected_etag"),
    [
        pytest.param(None, None, None, id="no_headers"),
        pytest.param([], None, None, id="empty"),
        pytest.param(['ETag: W/"7"'], None, 'W/"7"', id="etag_only"),
        pytest.param(
            ["Last-Modified: 2020-11-10", 'ETag: W/"1"'],
            datetime(2020, 11, 10, tzinfo=UTC),
            'W/"1"',
            id="naive_date_gets_utc",
        ),
        pytest.param(["Last-Modified: not a date"], None, None, id="invalid_date"),
        pytest.param(
            ["Content-Type: application/fhir+json", "Last-Modified: Tue, 10 Nov 2020 08:00:00 GMT"],
            # the header value is cut at the first colon, as before
            datetime(2020, 11, 10, 8, 0, tzinfo=UTC),
            None,
            id="http_date",
        ),
    ],
)
def test_values_are_the_same_on_every_call(
    headers: list[str] | None, expected_last_modified: datetime | None, expected_etag: str | None
) -> None:
    # Arrange
    response = _response(headers)

    # Act
    values = [(response.lastModified, response.etag) for _ in range(3)]

    # Assert
    assert values == [(expected_last_modified, expected_etag)] * 3


def test_last_modified_is_parsed_once_for_all_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: a list response creates one bundle entry per resource, each with lastModified and etag
    calls: list[str] = []
    real_parse = parser.parse

    def counting_parse(value: str, *args: Any, **kwargs: Any) -> datetime:
        calls.append(value)
        return cast(datetime, real_parse(value, *args, **kwargs))

    # dateutil is the third-party parser behind lastModified
    monkeypatch.setattr(parser, "parse", counting_parse)
    resources = [{"resourceType": "Observation", "id": str(i)} for i in range(5)]
    response = _response(["Last-Modified: 2020-11-10"], body=resources)

    # Act
    entries = [list(response.get_bundle_entries()) for _ in range(2)]

    # Assert
    assert len(calls) == 1
    assert {entry.response.lastModified for run in entries for entry in run if entry.response} == {
        datetime(2020, 11, 10, tzinfo=UTC)
    }


@pytest.mark.parametrize(
    "change_headers",
    [
        pytest.param(lambda r: r.response_headers.append('ETag: W/"2"'), id="append_in_place"),
        pytest.param(
            lambda r: setattr(r, "response_headers", ["Last-Modified: 2021-01-01", 'ETag: W/"2"']), id="reassign"
        ),
    ],
)
def test_new_headers_are_parsed_again(change_headers: Any) -> None:
    # Arrange
    response = _response(["Last-Modified: 2020-11-10"])
    assert response.etag is None

    # Act
    change_headers(response)

    # Assert
    assert response.etag == 'W/"2"'
    assert response.lastModified in (datetime(2020, 11, 10, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC))


def test_header_without_colon_still_raises_for_last_modified() -> None:
    # The lastModified loop has always split every header on ":"; that is kept, and an error is not cached
    response = _response(["no-colon-header", "Last-Modified: 2020-11-10"])

    for _ in range(2):
        with pytest.raises(IndexError):
            _ = response.lastModified
    assert response.etag is None
