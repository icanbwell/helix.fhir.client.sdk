"""Contract test for the text format of FhirGetSingleResponse.get_response_text().

compressedfhir 5.x json() is compact raw UTF-8 (3.x/4.x used ", " and ": " separators and, in 4.x,
\\uXXXX escapes). Consumers that hash, compare or persist this text see the change, so the exact
string is pinned here. Other tests compare parsed JSON and would not notice a format change.
"""

import pytest
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.get.fhir_get_single_response import (
    FhirGetSingleResponse,
)


@pytest.mark.parametrize(
    "response_text, expected_text",
    [
        pytest.param(
            '{"resourceType": "Patient", "id": "1"}',
            '{"resourceType":"Patient","id":"1"}',
            id="compact_separators",
        ),
        pytest.param(
            '{"resourceType": "Patient", "id": "1", "name": [{"family": "M\\u00fcller \\u5c71"}]}',
            '{"resourceType":"Patient","id":"1","name":[{"family":"Müller 山"}]}',
            id="raw_utf8_not_escaped",
        ),
    ],
)
def test_get_response_text_is_compact_raw_utf8(response_text: str, expected_text: str) -> None:
    response = FhirGetSingleResponse(
        request_id=None,
        url="http://example.com/Patient/1",
        response_text=response_text,
        error=None,
        access_token=None,
        total_count=1,
        status=200,
        extra_context_to_return=None,
        resource_type="Patient",
        id_="1",
        response_headers=None,
        results_by_url=[],
        storage_mode=CompressedDictStorageMode(),
    )

    assert response.get_response_text() == expected_text
