"""
The SDK calculates RequestCacheEntry.raw_hash only for a cache that keeps its entries.

A RequestCache with clear_cache_at_the_end set clears its entries when the traversal starts and when it ends. That
is the private cache the SDK makes when no input_cache is passed, and a caller's RequestCache() with the default.
No code can read the raw_hash values of such a cache, so the SDK doesn't calculate them. A cache that keeps its
entries (clear_cache_at_the_end False or None) can be saved and compared on a later run, so its stored raw_hash
values, the remove path and the results stay as they were. Only the HTTP boundary is mocked (mock-server). All data
is synthetic.
"""

import copy
import hashlib
import inspect
import json
from dataclasses import fields
from types import TracebackType
from typing import Any, Literal

import pytest
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from mockserver_client.mockserver_client import (
    MockServerFriendlyClient,
    mock_request,
    mock_response,
    times_any,
)

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.get.fhir_get_bundle_response import (
    FhirGetBundleResponse,
)
from helix_fhir_client_sdk.utilities.cache.request_cache import RequestCache
from helix_fhir_client_sdk.utilities.cache.request_cache_entry import RequestCacheEntry
from helix_fhir_client_sdk.utilities.hash_util import ResourceHash
from tests.logger_for_test import LoggerForTest

MOCK_SERVER_URL = "http://mock-server:1080"

EntryPoint = Literal[
    "simulate_graph_async",
    "simulate_graph_streaming_async",
    "simulate_graph_by_resource_type_async",
]
# none: no input_cache. default: RequestCache(), which clears its entries at the start and the end.
# empty and seeded: RequestCache(clear_cache_at_the_end=False), which keeps them; empty_flag_none: the same with None.
CacheKind = Literal["none", "default", "empty", "empty_flag_none", "seeded"]

# One graph that reaches every place where the SDK adds a fetched resource to the cache:
# the start resource read by id, a forward link with two ids in one ?_id= request, a forward link to an id the
# server does not have (404), a reverse link by parameters, and a nested forward link whose ?_id= request is
# refused (403), so the SDK reads those ids one by one (one of them is 404).
GRAPH: dict[str, Any] = {
    "resourceType": "GraphDefinition",
    "id": "raw-hash-matrix",
    "name": "raw_hash_matrix",
    "status": "active",
    "start": "Patient",
    "link": [
        {"path": "generalPractitioner[x]", "target": [{"type": "Practitioner"}]},
        {"path": "managingOrganization", "target": [{"type": "Organization"}]},
        {"target": [{"type": "Encounter", "params": "patient={ref}"}]},
        {
            "target": [
                {
                    "type": "DocumentReference",
                    "params": "patient={ref}",
                    "link": [{"path": "content[x].attachment.url", "target": [{"type": "Binary"}]}],
                }
            ]
        },
    ],
}

PATIENT: dict[str, Any] = {
    "resourceType": "Patient",
    "id": "1",
    "generalPractitioner": [{"reference": "Practitioner/5"}, {"reference": "Practitioner/6"}],
    "managingOrganization": {"reference": "Organization/99"},
}
PRACTITIONER_5: dict[str, Any] = {"resourceType": "Practitioner", "id": "5"}
PRACTITIONER_6: dict[str, Any] = {"resourceType": "Practitioner", "id": "6"}
ENCOUNTER_8: dict[str, Any] = {"resourceType": "Encounter", "id": "8", "status": "finished"}
ENCOUNTER_10: dict[str, Any] = {"resourceType": "Encounter", "id": "10", "status": "finished"}
# The version of Encounter/10 that a previous run saved; the server now returns ENCOUNTER_10.
ENCOUNTER_10_SAVED: dict[str, Any] = {"resourceType": "Encounter", "id": "10", "status": "in-progress"}
# Encounter/11 has an empty element. FhirResource.json() leaves it out, so raw_hash is the hash of
# ENCOUNTER_11_HASHED, while the returned resource keeps the element, whether or not the hash ran.
ENCOUNTER_11_HASHED: dict[str, Any] = {"resourceType": "Encounter", "id": "11", "status": "planned"}
ENCOUNTER_11: dict[str, Any] = ENCOUNTER_11_HASHED | {"reasonCode": []}
ENCOUNTER_12: dict[str, Any] = {"resourceType": "Encounter", "id": "12", "status": "planned"}
DOCUMENT_REFERENCE_20: dict[str, Any] = {
    "resourceType": "DocumentReference",
    "id": "20",
    "content": [
        {"attachment": {"url": "Binary/12"}},
        {"attachment": {"url": "Binary/13"}},
        {"attachment": {"url": "Binary/14"}},
    ],
}
BINARY_12: dict[str, Any] = {"resourceType": "Binary", "id": "12", "contentType": "text/plain"}
BINARY_14: dict[str, Any] = {"resourceType": "Binary", "id": "14", "contentType": "text/plain"}

SERVED: dict[str, dict[str, Any]] = {
    f"{resource['resourceType']}/{resource['id']}": resource
    for resource in (
        PATIENT,
        PRACTITIONER_5,
        PRACTITIONER_6,
        ENCOUNTER_8,
        ENCOUNTER_10,
        ENCOUNTER_11,
        DOCUMENT_REFERENCE_20,
        BINARY_12,
        BINARY_14,
    )
}

# The order in which every entry point returns the resources when max_concurrent_tasks is 1.
SEQUENTIAL_ORDER: list[str] = [
    "Patient/1",
    "Practitioner/5",
    "Practitioner/6",
    "Encounter/8",
    "Encounter/10",
    "Encounter/11",
    "DocumentReference/20",
    "Binary/12",
    "Binary/14",
]

# The same HTTP calls in every case of this module.
EXPECTED_REQUESTS: list[str] = sorted(
    [
        "GET /Patient/1",
        "GET /Practitioner?_id=5,6",
        "GET /Organization/99",
        "GET /Encounter?patient=1",
        "GET /DocumentReference?patient=1",
        "GET /Binary?_id=12,13",
        "GET /Binary/12",
        "GET /Binary/13",
        "GET /Binary/14",
    ]
)

ENTRY_POINTS_AND_COMPARE_HASH = [
    pytest.param(
        entry_point,
        compare_hash,
        id=f"{entry_point}-compare_hash_{'not_passed' if compare_hash is None else compare_hash}",
    )
    for entry_point, compare_hash in (
        ("simulate_graph_async", None),
        ("simulate_graph_async", True),
        ("simulate_graph_async", False),
        ("simulate_graph_streaming_async", None),  # it has no compare_hash parameter
        ("simulate_graph_by_resource_type_async", None),
        ("simulate_graph_by_resource_type_async", True),
        ("simulate_graph_by_resource_type_async", False),
    )
]


def golden_raw_hash(resource: dict[str, Any]) -> str:
    """The raw_hash value the SDK has always stored for a resource: sha256 of its JSON with sorted keys."""
    return hashlib.sha256(json.dumps(resource, sort_keys=True).encode("utf-8")).hexdigest()


# Reads a raw_hash value back as the resource it belongs to, so a failed assertion names resources, not digests.
RESOURCE_BY_RAW_HASH: dict[str, str] = {
    golden_raw_hash(resource): key for key, resource in (SERVED | {"Encounter/11": ENCOUNTER_11_HASHED}).items()
} | {golden_raw_hash(ENCOUNTER_10_SAVED): "Encounter/10 (saved version)"}


def resource_names(raw_hashes: list[str]) -> list[str]:
    return sorted(RESOURCE_BY_RAW_HASH.get(raw_hash, raw_hash) for raw_hash in raw_hashes)


@pytest.fixture
def hash_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Spy on ResourceHash.hash_value: calls the real method and records every digest it returns.

    Used only where no hash at all is the behavior under test. Elsewhere the tests assert the stored raw_hash values.
    """
    calls: list[str] = []
    real_hash_value = ResourceHash.hash_value

    def recording_hash_value(self: ResourceHash, value: str) -> str:
        digest = real_hash_value(self, value)
        calls.append(digest)
        return digest

    monkeypatch.setattr(ResourceHash, "hash_value", recording_hash_value)
    return calls


def searchset(*resources: dict[str, Any]) -> dict[str, Any]:
    return {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": r} for r in resources]}


def serve_synthetic_patient(case_path: str) -> MockServerFriendlyClient:
    """Resets the mock server and serves the synthetic patient's resources under /{case_path}."""
    mock_client = MockServerFriendlyClient(base_url=MOCK_SERVER_URL)
    mock_client.reset()

    def expect(
        path: str, *, code: int = 200, body: dict[str, Any] | None = None, query: dict[str, str] | None = None
    ) -> None:
        mock_client.expect(
            request=mock_request(path=f"/{case_path}/{path}", method="GET", querystring=query),
            response=mock_response(code=code, body=body),
            timing=times_any(),
        )

    expect("Patient/1", body=PATIENT)
    expect("Practitioner", query={"_id": "5,6"}, body=searchset(PRACTITIONER_5, PRACTITIONER_6))
    expect("Organization/99", code=404)
    expect("Encounter", query={"patient": "1"}, body=searchset(ENCOUNTER_8, ENCOUNTER_10, ENCOUNTER_11))
    expect("DocumentReference", query={"patient": "1"}, body=searchset(DOCUMENT_REFERENCE_20))
    expect("Binary", query={"_id": "12,13"}, code=403)
    expect("Binary/12", body=BINARY_12)
    expect("Binary/13", code=404)
    expect("Binary/14", body=BINARY_14)
    return mock_client


def recorded_requests(mock_client: MockServerFriendlyClient, case_path: str) -> list[str]:
    """Every request the mock server received, as 'GET /Type/id?name=value', sorted."""
    recorded: list[str] = []
    for request in mock_client.retrieve_requests():
        query = MockServerFriendlyClient.normalize_querystring_params(querystring_params=request.querystring_params)
        query_text = "&".join(f"{name}={','.join(values)}" for name, values in sorted((query or {}).items()))
        path = (request.path or "").removeprefix(f"/{case_path}")
        recorded.append(f"{request.method} {path}" + (f"?{query_text}" if query_text else ""))
    return sorted(recorded)


async def seed_saved_encounters(cache: RequestCache) -> RequestCache:
    """Loads what a previous run saved: Encounter/8 unchanged since then, and an older version of Encounter/10."""
    for resource in (ENCOUNTER_8, ENCOUNTER_10_SAVED):
        await cache.add_async(
            resource_type=resource["resourceType"],
            resource_id=resource["id"],
            bundle_entry=None,
            status=200,
            last_modified=None,
            etag=None,
            from_input_cache=True,
            raw_hash=golden_raw_hash(resource),
        )
    return cache


async def input_cache_for(cache_kind: CacheKind) -> RequestCache | None:
    if cache_kind == "none":
        return None
    if cache_kind == "default":
        return RequestCache()
    cache = RequestCache(clear_cache_at_the_end=None if cache_kind == "empty_flag_none" else False)
    return await seed_saved_encounters(cache) if cache_kind == "seeded" else cache


class CacheWithoutClearSetting(RequestCache):
    """A cache with no _clear_cache_at_the_end, like a subclass that skips RequestCache.__init__, a duck-typed cache
    or one unpickled from an older SDK. It keeps its entries, as RequestCache(clear_cache_at_the_end=False) does."""

    def __init__(self) -> None:  # does not call RequestCache.__init__, so _clear_cache_at_the_end is never set
        self.cache_hits = 0
        self.cache_misses = 0
        self._cache = {}

    async def __aenter__(self) -> "CacheWithoutClearSetting":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return None


async def run_entry_point(
    *,
    entry_point: EntryPoint,
    case_path: str,
    input_cache: RequestCache | None,
    compare_hash: bool | None,
    max_concurrent_tasks: int,
) -> list[FhirBundleEntry]:
    """Runs one public simulate_graph* method against the mock server and returns every bundle entry it returned."""
    fhir_client = FhirClient().expand_fhir_bundle(False)
    fhir_client.logger(logger=LoggerForTest())
    # With a token set, the client skips the SMART discovery request, whose result FhirClient caches per host for
    # the whole process; the requests of each case then don't depend on which test ran first.
    fhir_client = fhir_client.set_access_token("synthetic-access-token")
    fhir_client = fhir_client.url(f"{MOCK_SERVER_URL}/{case_path}").resource("Patient")
    arguments: dict[str, Any] = {
        "id_": "1",
        "graph_json": copy.deepcopy(GRAPH),
        "contained": False,
        "request_size": 2,
        "max_concurrent_tasks": max_concurrent_tasks,
        "input_cache": input_cache,
    }
    if compare_hash is not None:
        arguments["compare_hash"] = compare_hash
    if entry_point == "simulate_graph_async":
        response = await fhir_client.simulate_graph_async(**arguments)
        return list(response.get_bundle_entries())
    responses = (
        fhir_client.simulate_graph_streaming_async(**arguments)
        if entry_point == "simulate_graph_streaming_async"
        else fhir_client.simulate_graph_by_resource_type_async(**arguments)
    )
    return [entry async for response in responses for entry in response.get_bundle_entries()]


def returned_resources(entries: list[FhirBundleEntry]) -> list[tuple[str, dict[str, Any]]]:
    """(resourceType/id, content) for every returned resource except OperationOutcome, in returned order.

    The content is raw_dict(), which keeps empty elements, so the comparison would show any change that the
    hash's FhirResource.json() call made to a resource.
    """
    return [
        (f"{entry.resource.resource_type}/{entry.resource.id}", entry.resource.raw_dict())
        for entry in entries
        if entry.resource is not None and entry.resource.resource_type != "OperationOutcome"
    ]


def expected_returned_keys(cache_kind: CacheKind, compare_hash: bool | None = None) -> list[str]:
    # The seeded cache holds Encounter/8 unchanged, so the remove path drops it; the changed Encounter/10 stays.
    # With compare_hash False the remove path does not compare hashes, so it drops every key the seeded cache holds.
    removed = {"Encounter/8"} | ({"Encounter/10"} if compare_hash is False else set())
    return sorted(key for key in SERVED if not (cache_kind == "seeded" and key in removed))


async def stored_raw_hashes(cache: RequestCache) -> dict[str, tuple[str, bool]]:
    """resourceType/id -> (whose hash raw_hash is, from_input_cache) for every entry in the cache."""
    return {
        f"{entry.resource_type}/{entry.id_}": (
            RESOURCE_BY_RAW_HASH.get(entry.raw_hash, entry.raw_hash),
            bool(entry.from_input_cache),
        )
        async for entry in cache.get_entries_async()
    }


def expected_stored_raw_hashes(cache_kind: CacheKind, compare_hash: bool | None) -> dict[str, tuple[str, bool]]:
    """What a cache that keeps its entries holds after the traversal: the values the SDK has always stored."""
    # compare_hash reaches the start resource and every link fetch: with False nothing is hashed.
    stored: dict[str, tuple[str, bool]] = {key: (key if compare_hash is not False else "", False) for key in SERVED}
    if cache_kind == "seeded":
        # Encounter/8 is removed before the cache add, so the entry loaded from the saved cache stays.
        stored["Encounter/8"] = ("Encounter/8", True)
        if compare_hash is False:
            # Without the hash comparison the changed Encounter/10 is removed too, so its saved entry stays.
            stored["Encounter/10"] = ("Encounter/10 (saved version)", True)
    # The 404 entries (by-id fetch, and one-by-one read) never have a hash.
    return stored | {"Organization/99": ("", False), "Binary/13": ("", False)}


@pytest.mark.parametrize("cache_kind", ["none", "default"])
@pytest.mark.parametrize("max_concurrent_tasks", [1, 15])
@pytest.mark.parametrize(("entry_point", "compare_hash"), ENTRY_POINTS_AND_COMPARE_HASH)
async def test_no_raw_hash_for_a_cache_cleared_at_the_end(
    entry_point: EntryPoint,
    compare_hash: bool | None,
    max_concurrent_tasks: int,
    cache_kind: CacheKind,
    hash_calls: list[str],
) -> None:
    case_path = f"raw_hash_cleared_{cache_kind}_{entry_point}_{compare_hash}_{max_concurrent_tasks}"
    mock_client = serve_synthetic_patient(case_path)
    input_cache = await input_cache_for(cache_kind)

    entries = await run_entry_point(
        entry_point=entry_point,
        case_path=case_path,
        input_cache=input_cache,
        compare_hash=compare_hash,
        max_concurrent_tasks=max_concurrent_tasks,
    )

    returned = returned_resources(entries)
    assert sorted(key for key, _ in returned) == expected_returned_keys(cache_kind)
    assert all(resource == SERVED[key] for key, resource in returned)
    if max_concurrent_tasks == 1:
        assert [key for key, _ in returned] == SEQUENTIAL_ORDER
    assert recorded_requests(mock_client, case_path) == EXPECTED_REQUESTS
    # The caller's default RequestCache() is empty afterwards, like the SDK's own cache: nothing can read a hash.
    assert input_cache is None or len(input_cache) == 0
    assert resource_names(hash_calls) == []


@pytest.mark.parametrize("cache_kind", ["empty", "empty_flag_none", "seeded"])
@pytest.mark.parametrize("max_concurrent_tasks", [1, 15])
@pytest.mark.parametrize(("entry_point", "compare_hash"), ENTRY_POINTS_AND_COMPARE_HASH)
async def test_persisted_input_cache_keeps_raw_hash_values_and_remove_path(
    entry_point: EntryPoint,
    compare_hash: bool | None,
    max_concurrent_tasks: int,
    cache_kind: CacheKind,
) -> None:
    case_path = f"raw_hash_persisted_{cache_kind}_{entry_point}_{compare_hash}_{max_concurrent_tasks}"
    mock_client = serve_synthetic_patient(case_path)
    input_cache = await input_cache_for(cache_kind)
    assert input_cache is not None

    entries = await run_entry_point(
        entry_point=entry_point,
        case_path=case_path,
        input_cache=input_cache,
        compare_hash=compare_hash,
        max_concurrent_tasks=max_concurrent_tasks,
    )

    returned = returned_resources(entries)
    assert await stored_raw_hashes(input_cache) == expected_stored_raw_hashes(cache_kind, compare_hash)
    assert sorted(key for key, _ in returned) == expected_returned_keys(cache_kind, compare_hash)
    assert all(resource == SERVED[key] for key, resource in returned)
    assert recorded_requests(mock_client, case_path) == EXPECTED_REQUESTS


@pytest.mark.parametrize("cache_kind", ["empty", "empty_flag_none"])
@pytest.mark.parametrize("max_concurrent_tasks", [1, 15])
@pytest.mark.parametrize(
    ("entry_point", "compare_hash", "expected_hashed"),
    [
        pytest.param("simulate_graph_async", False, [], id="simulate_graph_async-compare_hash_false"),
        pytest.param(
            "simulate_graph_by_resource_type_async",
            False,
            [],
            id="simulate_graph_by_resource_type_async-compare_hash_false",
        ),
        pytest.param(
            "simulate_graph_async",
            True,
            sorted(SERVED),
            id="simulate_graph_async-compare_hash_true",
        ),
        pytest.param(
            "simulate_graph_by_resource_type_async",
            None,
            sorted(SERVED),
            id="simulate_graph_by_resource_type_async-compare_hash_not_passed",
        ),
    ],
)
async def test_compare_hash_false_skips_hashing_on_link_fetches(
    entry_point: EntryPoint,
    compare_hash: bool | None,
    expected_hashed: list[str],
    max_concurrent_tasks: int,
    cache_kind: CacheKind,
    hash_calls: list[str],
) -> None:
    # Arrange
    case_path = f"raw_hash_link_fetches_{cache_kind}_{entry_point}_{compare_hash}_{max_concurrent_tasks}"
    mock_client = serve_synthetic_patient(case_path)
    input_cache = await input_cache_for(cache_kind)

    # Act
    entries = await run_entry_point(
        entry_point=entry_point,
        case_path=case_path,
        input_cache=input_cache,
        compare_hash=compare_hash,
        max_concurrent_tasks=max_concurrent_tasks,
    )

    # Assert: the start resource and every linked resource are hashed only when compare_hash is not False
    # (some resources are hashed more than once, so compare the set of hashed resources)
    assert sorted(set(resource_names(hash_calls))) == expected_hashed
    returned = returned_resources(entries)
    assert sorted(key for key, _ in returned) == expected_returned_keys(cache_kind)
    assert all(resource == SERVED[key] for key, resource in returned)
    assert recorded_requests(mock_client, case_path) == EXPECTED_REQUESTS


@pytest.mark.parametrize(
    "entry_point",
    ["simulate_graph_async", "simulate_graph_streaming_async", "simulate_graph_by_resource_type_async"],
)
async def test_cache_without_the_clear_setting_hashes_as_today(entry_point: EntryPoint) -> None:
    case_path = f"raw_hash_cache_without_clear_setting_{entry_point}"
    mock_client = serve_synthetic_patient(case_path)
    input_cache = CacheWithoutClearSetting()

    entries = await run_entry_point(
        entry_point=entry_point,
        case_path=case_path,
        input_cache=input_cache,
        compare_hash=None,
        max_concurrent_tasks=1,
    )

    returned = returned_resources(entries)
    assert await stored_raw_hashes(input_cache) == expected_stored_raw_hashes("empty", None)
    assert sorted(key for key, _ in returned) == expected_returned_keys("empty")
    assert all(resource == SERVED[key] for key, resource in returned)
    assert recorded_requests(mock_client, case_path) == EXPECTED_REQUESTS


@pytest.mark.parametrize(
    ("compare_hash", "expected_kept"),
    [
        pytest.param(True, ["Encounter/10", "Encounter/11", "Encounter/12"], id="compare_hash_true-removes_unchanged"),
        pytest.param(False, ["Encounter/11", "Encounter/12"], id="compare_hash_false-removes_every_loaded_key"),
    ],
)
async def test_remove_entries_in_cache_meaning_of_compare_hash(compare_hash: bool, expected_kept: list[str]) -> None:
    cache = await seed_saved_encounters(RequestCache(clear_cache_at_the_end=False))
    # Fetched earlier in the same run, not loaded from a saved cache: the remove path ignores it.
    await cache.add_async(
        resource_type="Encounter",
        resource_id="11",
        bundle_entry=None,
        status=200,
        last_modified=None,
        etag=None,
        from_input_cache=False,
        raw_hash=golden_raw_hash(ENCOUNTER_11_HASHED),
    )
    response = FhirGetBundleResponse(
        request_id=None,
        url="http://mock-server:1080/remove_path/Encounter",
        response_text=json.dumps(searchset(ENCOUNTER_8, ENCOUNTER_10, ENCOUNTER_11, ENCOUNTER_12)),
        error=None,
        access_token=None,
        total_count=None,
        status=200,
        extra_context_to_return=None,
        resource_type="Encounter",
        id_=None,
        response_headers=None,
        results_by_url=[],
        storage_mode=CompressedDictStorageMode.raw(),
    )

    await response.remove_entries_in_cache_async(request_cache=cache, compare_hash=compare_hash, logger=None)

    assert [key for key, _ in returned_resources(list(response.get_bundle_entries()))] == expected_kept


def test_request_cache_constructor_and_entry_are_unchanged() -> None:
    parameters = [
        (parameter.name, parameter.kind, parameter.default, parameter.annotation)
        for parameter in inspect.signature(RequestCache).parameters.values()
    ]
    raw_hash_type = {field.name: field.type for field in fields(RequestCacheEntry)}["raw_hash"]

    assert parameters == [
        ("initial_dict", inspect.Parameter.KEYWORD_ONLY, None, dict[str, Any] | None),
        ("clear_cache_at_the_end", inspect.Parameter.KEYWORD_ONLY, True, bool | None),
    ]
    assert raw_hash_type is str
