import hashlib
from typing import Any

import pytest
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.utilities.hash_util import ResourceHash, stable_resource_hash_input

# Synthetic resources (no PHI).
_FIXED: dict[str, Any] = {
    "resourceType": "Observation",
    "id": "obs-1",
    "status": "final",
    "code": {"text": "Zoë Ångström 日本語"},
    "valueQuantity": {"value": 1.5, "unit": "mg"},
    "note": [{"text": "line sep"}],
}
_WITH_NAN: dict[str, Any] = {
    "resourceType": "Observation",
    "id": "obs-2",
    "status": "final",
    "valueQuantity": {"value": float("nan"), "unit": "mg"},
}


@pytest.mark.parametrize(
    "resource_dict, expected_hash",
    [
        # The first digest was captured on main before the compressedfhir 5.0.0 upgrade (compressedfhir 3.0.5),
        # so they prove continuity with raw_hash values callers may already have persisted.
        (_FIXED, "a96413ba26f659be4d2a0baaadd704eb3636e2ead1cccbe21d70463f33df6c78"),  # pragma: allowlist secret
        # compressedfhir 5.0.0 drops a NaN value from json() in both modes, where 3.0.5 wrote a NaN literal
        # (3.0.5 digest: c4698c501b30838dc1ad75aae09d166a1cbaf30dcd2fd57d09017ae7d38d867a), so a resource holding
        # NaN hashes differently after the upgrade whatever the client option is.  This pins the 5.0.0 value
        # and proves the hash is the same in both client modes.
        (_WITH_NAN, "f912fe26092d3864e1192a665a1ce74383eaeff7fb823cb93b9df0ab2e5494d5"),  # pragma: allowlist secret
    ],
)
def test_resource_hash_matches_value_captured_before_the_upgrade(
    resource_dict: dict[str, Any], expected_hash: str
) -> None:
    resource = FhirResource(initial_dict=resource_dict, storage_mode=CompressedDictStorageMode.default())

    actual = ResourceHash().hash_value(stable_resource_hash_input(resource))

    assert actual == expected_hash


def test_hash_input_is_independent_of_the_default_json_text() -> None:
    resource = FhirResource(initial_dict=_WITH_NAN, storage_mode=CompressedDictStorageMode.default())

    default_text_hash = hashlib.sha256(resource.json().encode("utf-8")).hexdigest()
    stable_hash = hashlib.sha256(stable_resource_hash_input(resource).encode("utf-8")).hexdigest()

    assert stable_hash != default_text_hash
