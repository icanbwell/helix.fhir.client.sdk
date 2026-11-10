import json
import uuid
from collections import OrderedDict
from typing import Any

from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from compressedfhir.utilities.fhir_json_encoder import FhirJSONEncoder
from compressedfhir.utilities.json_helpers import FhirClientJsonHelpers

_JSON_SCALAR_TYPES: frozenset[type] = frozenset({str, int, float, bool, type(None)})


def _is_plain_json(value: Any) -> bool:
    """
    True if value holds only dict/OrderedDict with str keys, list, str, int, float, bool and None (exact types).
    For such a value json.loads(json.dumps(value)) gives back an equal value and json.dumps() never calls the
    encoder's default(), so serializing it once gives the same text as the dict() round trip does.
    """
    stack: list[Any] = [value]
    while stack:
        item = stack.pop()
        item_type = type(item)
        if item_type is dict or item_type is OrderedDict:
            for key, child in item.items():
                if type(key) is not str:
                    return False
                stack.append(child)
        elif item_type is list:
            stack.extend(item)
        elif item_type not in _JSON_SCALAR_TYPES:
            return False
    return True


def _resource_json_if_plain(entry: FhirBundleEntry | None) -> str | None:
    """
    The entry's resource as JSON, serialized once from its raw dict, or None when the entry has anything but a
    resource or the resource holds anything but plain JSON values (so the caller falls back to FhirBundle.json()).
    """
    if entry is None or not isinstance(entry.resource, FhirResource):
        return None
    if (
        entry.fullUrl is not None
        or entry.request is not None
        or entry.response is not None
        or entry.link is not None
        or entry.search is not None
    ):
        return None
    raw_dict = entry.resource.raw_dict()
    if not _is_plain_json(raw_dict):
        return None
    cleaned = FhirClientJsonHelpers.remove_empty_elements_from_ordered_dict(raw_dict)
    if not cleaned:
        # FhirBundle.json() drops an entry whose resource is empty
        return None
    return json.dumps(obj=cleaned, cls=FhirJSONEncoder)


def _bundle_json_template(bundle: FhirBundle) -> tuple[str, str, str]:
    """
    Serializes the bundle's own fields with two marker entries and splits the text around them, so the
    entry list can be filled in without rebuilding the bundle: returns (prefix, separator, suffix) where
    the bundle text is prefix + separator.join(entry resource texts) + suffix.
    """
    markers: list[str] = [uuid.uuid4().hex, uuid.uuid4().hex]
    marker_texts: list[str] = [json.dumps({"resourceType": marker}) for marker in markers]
    template_bundle = FhirBundle(
        id_=bundle.id_,
        identifier=bundle.identifier,
        timestamp=bundle.timestamp,
        type_=bundle.type_,
        entry=FhirBundleEntryList(
            [
                FhirBundleEntry(
                    resource=FhirResource(
                        initial_dict={"resourceType": marker}, storage_mode=CompressedDictStorageMode.raw()
                    ),
                    storage_mode=CompressedDictStorageMode.raw(),
                )
                for marker in markers
            ]
        ),
        total=bundle.total,
        link=bundle.link,
        meta=bundle.meta,
    )
    template: str = template_bundle.json()
    prefix, rest = template.split(marker_texts[0])
    separator, suffix = rest.split(marker_texts[1])
    return prefix, separator, suffix


def fhir_bundle_json(bundle: FhirBundle) -> str:
    """
    Returns the same text as bundle.json(), without the resource.dict() round trip (serialize, parse,
    then serialize the whole bundle again) that FhirBundle.json() does for every resource.

    Each resource is serialized once and the texts are joined into the bundle text. This is used only when
    every entry holds just a resource with plain JSON values; otherwise it returns bundle.json().

    :param bundle: bundle to serialize
    :return: JSON text of the bundle, equal to bundle.json()
    """
    if not bundle.entry:
        return bundle.json()
    resource_texts: list[str] = []
    for entry in bundle.entry:
        resource_text = _resource_json_if_plain(entry)
        if resource_text is None:
            return bundle.json()
        resource_texts.append(resource_text)
    prefix, separator, suffix = _bundle_json_template(bundle)
    return prefix + separator.join(resource_texts) + suffix
