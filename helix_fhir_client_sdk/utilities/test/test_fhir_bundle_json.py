"""fhir_bundle_json(bundle) must return exactly bundle.json(): the $merge request body is unchanged byte for byte.
All data is synthetic."""

import json
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest
from aioresponses import aioresponses
from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_bundle_entry_request import FhirBundleEntryRequest
from compressedfhir.fhir.fhir_identifier import FhirIdentifier
from compressedfhir.fhir.fhir_link import FhirLink
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from yarl import URL

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.utilities.fhir_bundle_json import fhir_bundle_json

PATIENT: dict[str, Any] = {"resourceType": "Patient", "id": "p1", "active": True, "name": [{"family": "Synthetic"}]}
OBSERVATION: dict[str, Any] = {
    "resourceType": "Observation",
    "id": "o1",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "1234-5"}], "text": "Synthetic ü ✓"},
    "valueQuantity": {"value": 1.1, "unit": "mg"},
    "component": [{"valueInteger": 0}, {"valueBoolean": False}, {"valueDecimal": -0.0}],
}
WITH_EMPTY_ELEMENTS: dict[str, Any] = {
    "resourceType": "Encounter",
    "id": "e1",
    "status": "planned",
    "reasonCode": [],
    "note": [{"text": "  "}, {}],
    "period": {"start": None, "end": "2020-01-01"},
    "extension": [{"url": "https://example.com/x", "valueString": ""}],
}
LARGE_NUMBERS: dict[str, Any] = {
    "resourceType": "Observation",
    "id": "o2",
    "valueQuantity": {"value": 12345678901234567890, "comparator": "<"},
    "valueRange": {"low": {"value": 1e-7}, "high": {"value": 1.7976931348623157e308}},
}

PLAIN_RESOURCES: list[dict[str, Any]] = [PATIENT, OBSERVATION, WITH_EMPTY_ELEMENTS, LARGE_NUMBERS]
STORAGE_MODES = [CompressedDictStorageMode.raw(), CompressedDictStorageMode.compressed()]


def bundle_of(resources: list[dict[str, Any]], storage_mode: CompressedDictStorageMode, **fields: Any) -> FhirBundle:
    return FhirBundle(
        type_=fields.pop("type_", "collection"),
        entry=FhirBundleEntryList(
            [
                FhirBundleEntry(
                    resource=FhirResource(initial_dict=OrderedDict(r), storage_mode=storage_mode),
                    storage_mode=storage_mode,
                )
                for r in resources
            ]
        ),
        **fields,
    )


BUNDLE_FIELDS: list[Any] = [
    pytest.param({}, id="no_bundle_fields"),
    pytest.param({"type_": "batch", "id_": "b1", "timestamp": "2020-01-01T00:00:00Z", "total": 4}, id="id_ts_total"),
    pytest.param(
        {
            "identifier": FhirIdentifier(system="https://example.com/ids", value="v1"),
            "link": [FhirLink(relation="self", url="https://example.com/Bundle/b1")],
        },
        id="identifier_and_link",
    ),
]


@pytest.mark.parametrize("storage_mode", STORAGE_MODES, ids=["raw", "compressed"])
@pytest.mark.parametrize("bundle_fields", BUNDLE_FIELDS)
@pytest.mark.parametrize(
    "resources",
    [
        pytest.param(PLAIN_RESOURCES, id="mixed"),
        pytest.param([PATIENT, PATIENT], id="duplicates"),
        pytest.param([PATIENT], id="one"),
        pytest.param([WITH_EMPTY_ELEMENTS] * 3, id="empty_elements"),
    ],
)
def test_plain_resources_give_the_same_text_as_bundle_json(
    resources: list[dict[str, Any]], bundle_fields: dict[str, Any], storage_mode: CompressedDictStorageMode
) -> None:
    # Arrange
    bundle = bundle_of(resources, storage_mode, **dict(bundle_fields))

    # Act
    text = fhir_bundle_json(bundle)

    # Assert
    assert text == bundle.json()


def _entry_with_request() -> FhirBundleEntry:
    return FhirBundleEntry(resource=FhirResource(PATIENT), request=FhirBundleEntryRequest(url="Patient/p1"))


@pytest.mark.parametrize("storage_mode", STORAGE_MODES, ids=["raw", "compressed"])
@pytest.mark.parametrize(
    "odd_entry",
    [
        pytest.param(lambda: _entry_with_request(), id="entry_with_request"),
        pytest.param(lambda: FhirBundleEntry(resource=FhirResource(PATIENT), fullUrl="urn:uuid:1"), id="full_url"),
        pytest.param(
            lambda: FhirBundleEntry(resource=FhirResource(PATIENT | {"birthDate": datetime(2000, 1, 2)})),
            id="datetime_value",
        ),
        pytest.param(lambda: FhirBundleEntry(resource=FhirResource(PATIENT | {"x": Decimal("1.50")})), id="decimal"),
        pytest.param(lambda: FhirBundleEntry(resource=FhirResource(PATIENT | {"x": ()})), id="empty_tuple"),
        pytest.param(lambda: FhirBundleEntry(resource=FhirResource(PATIENT | {"x": (None, "a")})), id="tuple"),
        pytest.param(lambda: FhirBundleEntry(resource=FhirResource(PATIENT | {"x": set()})), id="empty_set"),
        pytest.param(lambda: FhirBundleEntry(resource=FhirResource(PATIENT | {"x": b""})), id="empty_bytes"),
        pytest.param(lambda: FhirBundleEntry(resource=FhirResource(PATIENT | {"x": {1: "a"}})), id="int_key"),
        pytest.param(lambda: FhirBundleEntry(resource=FhirResource({"id": None, "x": []})), id="empty_resource"),
    ],
)
def test_other_content_falls_back_to_bundle_json(odd_entry: Any, storage_mode: CompressedDictStorageMode) -> None:
    # Arrange: plain resources around one entry that the fast path does not handle
    bundle = bundle_of([PATIENT, OBSERVATION], storage_mode)
    bundle.entry.append(odd_entry())

    # Act
    text = fhir_bundle_json(bundle)

    # Assert
    assert text == bundle.json()


class _TaggedResource(FhirResource):
    """A resource subclass whose dict() adds a field, so its serialized text differs from its raw dict."""

    def dict(self) -> OrderedDict[str, Any]:
        result = super().dict()
        result["implicitRules"] = "https://example.com/tagged-resource"
        return result


class _TaggedEntry(FhirBundleEntry):
    """An entry subclass whose dict() adds a field."""

    def dict(self) -> OrderedDict[str, Any]:
        result = super().dict()
        result["fullUrl"] = "urn:uuid:tagged-entry"
        return result


class _TaggedBundle(FhirBundle):
    """A bundle subclass whose json() adds a field."""

    def json(self) -> str:
        return json.dumps({"tagged": True, **json.loads(super().json())})


@pytest.mark.parametrize(
    "bundle_factory, marker",
    [
        pytest.param(
            lambda: FhirBundle(
                type_="collection",
                entry=FhirBundleEntryList(
                    [
                        FhirBundleEntry(resource=FhirResource(PATIENT)),
                        FhirBundleEntry(resource=_TaggedResource(PATIENT)),
                    ]
                ),
            ),
            "tagged-resource",
            id="resource_subclass",
        ),
        pytest.param(
            lambda: FhirBundle(
                type_="collection",
                entry=FhirBundleEntryList(
                    [FhirBundleEntry(resource=FhirResource(PATIENT)), _TaggedEntry(resource=FhirResource(PATIENT))]
                ),
            ),
            "tagged-entry",
            id="entry_subclass",
        ),
        pytest.param(
            lambda: _TaggedBundle(
                type_="collection",
                entry=FhirBundleEntryList(
                    [
                        FhirBundleEntry(resource=FhirResource(PATIENT)),
                        FhirBundleEntry(resource=FhirResource(OBSERVATION)),
                    ]
                ),
            ),
            '"tagged": true',
            id="bundle_subclass",
        ),
    ],
)
def test_subclasses_fall_back_to_their_own_serialization(bundle_factory: Any, marker: str) -> None:
    # Arrange: a subclass that overrides dict()/json() must be serialized through its own methods
    bundle = bundle_factory()

    # Act
    text = fhir_bundle_json(bundle)

    # Assert
    assert marker in text
    assert text == bundle.json()


def test_empty_bundle_gives_the_same_text_as_bundle_json() -> None:
    bundle = FhirBundle(type_="collection")

    assert fhir_bundle_json(bundle) == bundle.json()


@pytest.mark.asyncio
async def test_merge_bundle_body_is_bundle_json() -> None:
    # Arrange
    url = "http://example.com/Patient/1/$merge"
    fhir_client = FhirClient().url("http://example.com").resource("Patient")
    bundle = bundle_of(PLAIN_RESOURCES, CompressedDictStorageMode.raw(), id_="b1")
    expected_body = bundle.json()

    with aioresponses() as m:
        m.post(url, status=200, payload=[{"id": "p1", "created": True}])

        # Act
        _ = [response async for response in fhir_client.merge_bundle_async(id_="1", bundle=bundle)]

        # Assert
        data = m.requests[("POST", URL(url))][-1].kwargs["data"]
        body = data if isinstance(data, str) else data.decode("utf-8")
        assert body == expected_body
        assert json.loads(body)["entry"][0]["resource"] == PATIENT
