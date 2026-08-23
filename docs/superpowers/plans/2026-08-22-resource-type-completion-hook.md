# Per-Resource-Type Completion Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give callers of `simulate_graph_by_resource_type_async()` a full connect → progress → done event lifecycle: an explicit, concurrency-safe callback that fires each time one `GraphDefinition` link (i.e. one resource type, or occasionally a small set of them) has been *fully* retrieved (already implemented, Tasks 1-3), a matching callback that fires right *before* that same retrieval begins, and two whole-graph bookend callbacks marking the start and end of the entire traversal — so consumers can report real progress ("connecting... now retrieving Condition... done") without reverse-engineering completion from yield ordering.

**Architecture:** Four optional keyword-only parameters on `simulate_graph_by_resource_type_async()`, threaded down to the private generator `_process_simulate_graph_by_resource_type_async()`:
- `on_resource_type_completed` (Tasks 1-2, done): fires once for the start resource right after it's yielded, and once per outer-loop row right after that row's full `link_responses` list has been drained into individual yields.
- `on_resource_type_started` (Task 5): the "before" counterpart — fires once for the start resource right before it's fetched, and once per row right before that row's link begins retrieving. Because rows can run concurrently (`max_concurrent_tasks > 1`), this one cannot fire from the single-threaded outer generator loop like `on_resource_type_completed` does — it fires from inside `process_link_async_parallel_function` itself, the function `AsyncParallelProcessor` runs per row, threaded in via a new field on `GraphLinkParameters`.
- `on_graph_retrieval_started` (Task 5): fires exactly once, before the start resource is fetched — the first thing the method does.
- `on_graph_retrieval_completed` (Task 5): fires exactly once, after every resource in the graph has been yielded — the last thing the method does, carrying an aggregate summary (distinct resource types seen, total resource count, deepest graph_depth reached).

Resource type(s) and count are derived from the *actual* `FhirGetResponse.resource_type` / `get_resource_count()` values already present on each yielded response for the "completed"/whole-graph-completed events — not from the `GraphDefinition` — so those events reflect what was actually fetched. The two "started" events necessarily use the graph definition's *declared* target types instead, since nothing has been fetched yet at that point. No existing signature's *return type* changes; every new parameter defaults to `None` (no-op), so this is fully backward compatible.

**Tech Stack:** Python 3.12+, asyncio, this repo's existing `helix_fhir_client_sdk.graph.simulated_graph_processor_mixin` module.

**Spec:** Phase 2 of `docs/superpowers/specs/2026-08-22-data-connection-status-design.md` in `mcp-fhir-agent` (path at time of writing: `/Users/imranqureshi/git/mcp-fhir-agent/.claude/worktrees/IQ-EA-2509-view/docs/superpowers/specs/2026-08-22-data-connection-status-design.md`), §6. That doc assumed `simulate_graph_async()` had *no* per-resource-type hook at all. That's out of date for this method specifically: `simulate_graph_by_resource_type_async()` (added in commit `abdae63` "DCON-3865 Added fn to retrieve data in streaming way") already yields one `FhirGetResponse` per resource-type chunk, and `helix.pipelines` already consumes it by default for FHIR-based PROA connections (see the companion plan in `helix.pipelines`, Task 1, for the call-chain evidence). What's genuinely missing — and what this plan adds — is an *explicit* "this resource type is done" signal, because today a consumer can only infer completion by watching for `resource_type` to change between consecutive yields, which is only safe when `max_concurrent_tasks == 1` (the pipeline's own default, but not a documented contract of this method).

## Global Constraints

- Zero behavior change for existing callers: the new parameter is optional, defaults to `None`, and when `None` no new code path executes.
- No change to the yielded `FhirGetResponse` sequence, ordering, or count — this is purely an additional side channel.
- Must work correctly regardless of `max_concurrent_tasks` (i.e., don't bake in an assumption that rows complete in submission order) — this is the entire point of making the signal explicit instead of inferred.
- `on_resource_type_started` fires from inside `process_link_async_parallel_function` (a per-row task, potentially one of several running concurrently), unlike `on_resource_type_completed` which fires from the single-threaded outer generator loop. Do not assume `started` events across *different* links arrive in any particular relative order when `max_concurrent_tasks > 1` — only that a given link's own `started` event precedes that same link's own `completed` event, and that both whole-graph bookend events fire exactly once each, before/after everything else respectively, regardless of concurrency.
- `GraphLinkParameters` is also constructed by the unrelated `simulate_graph_async()` code path (`simulated_graph_processor_mixin.py:223`), which does not use `simulate_graph_by_resource_type_async`'s new hooks. Any new field added to `GraphLinkParameters` for this feature must have a default (so that unrelated call site needs no change) and must be a no-op when `None`/unset.
- Follow existing repo conventions: `from __future__` not used elsewhere in this module, so don't add it; use the same `dataclass(slots=True)` style already used for `ParallelFunctionContext` in `helix_fhir_client_sdk/utilities/async_parallel_processor/v1/async_parallel_processor.py`.
- Run `mypy`/whatever type-checker this repo uses (check `pyproject.toml` / `.pylintrc` / CI config) and `pytest` before each commit — this repo is a published dependency; a type error here breaks every consumer's build.

---

## Task 1: `ResourceTypeCompletionEvent` data type

**Files:**
- Create: `helix_fhir_client_sdk/graph/resource_type_completion_event.py`
- Test: `helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py` — confirmed convention: this module's sibling tests (`test_simulate_graph_processor_mixin.py`, `test_simulate_graph_processor_mixin_caching.py`) live in a `test/` subpackage next to the source, not under a top-level `tests/` dir. The repo-root `tests/` directory holds unrelated suites (`fhir/`, `async/`, `sync/`, `deidentifier/`).

**Interfaces:**
- Produces: `ResourceTypeCompletionEvent` dataclass with fields `resource_types: list[str]`, `resource_count: int`, `graph_depth: int` — consumed by Task 2.

- [ ] **Step 1: Write the failing test**

```python
from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)


def test_resource_type_completion_event_construction() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["Condition"],
        resource_count=12,
        graph_depth=1,
    )
    assert event.resource_types == ["Condition"]
    assert event.resource_count == 12
    assert event.graph_depth == 1


def test_resource_type_completion_event_multiple_types() -> None:
    # A single GraphDefinition link's `target` array can name more than one type
    # (e.g. a link with both AllergyIntolerance and CarePlan targets), so this
    # must accept more than one resource type per event.
    event = ResourceTypeCompletionEvent(
        resource_types=["AllergyIntolerance", "CarePlan"],
        resource_count=5,
        graph_depth=0,
    )
    assert len(event.resource_types) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'helix_fhir_client_sdk.graph.resource_type_completion_event'`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass(slots=True)
class ResourceTypeCompletionEvent:
    """
    Emitted by simulate_graph_by_resource_type_async() after every resource that
    belongs to one GraphDefinition link (usually one resource type, occasionally
    more than one if the link's `target` array names several types) has been
    yielded to the caller. There is nothing left to wait for regarding these
    resource type(s) at this graph depth once this event fires.
    """

    resource_types: list[str]
    """Distinct resource type(s) actually returned for the completed link, taken
    from each yielded FhirGetResponse.resource_type — not from the graph
    definition's declared target types, so this reflects what was actually
    fetched (e.g. empty results still fire with resource_types=[] filtered out
    upstream; see Task 2)."""

    resource_count: int
    """Total resource count across every FhirGetResponse chunk yielded for this
    link (sum of each chunk's get_resource_count())."""

    graph_depth: int
    """0 for links directly off the start resource; incremented once per pass
    through simulate_graph_by_resource_type_async's outer while loop, i.e. once
    per level of target.link nesting. A resource type can recur at a later
    depth (e.g. Practitioner reached both via Patient.generalPractitioner and,
    later, Encounter.participant) — callers should treat this as "retrieving
    again", not a bug."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add helix_fhir_client_sdk/graph/resource_type_completion_event.py helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py
git commit -m "DCON-4509 add ResourceTypeCompletionEvent for per-resource-type progress signaling"
```

---

## Task 2: Thread `on_resource_type_completed` through `simulate_graph_by_resource_type_async`

**Files:**
- Modify: `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py:1292-1499` (`simulate_graph_by_resource_type_async` and `_process_simulate_graph_by_resource_type_async`)
- Test: confirmed no existing tests reference `simulate_graph_by_resource_type_async` anywhere in the repo (`grep -rln "simulate_graph_by_resource_type_async" --include="*.py" .` returns only the source file itself). Create `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py`, mirroring the mocking pattern already used by `helix_fhir_client_sdk/graph/test/test_simulate_graph_processor_mixin.py` in the same directory (see below — there is no fixture-based mocking in this repo; it uses a `TestGraphProcessor(FhirClient)` subclass + `aioresponses()`).

**Interfaces:**
- Consumes: `ResourceTypeCompletionEvent` from Task 1.
- Produces: new keyword-only parameter `on_resource_type_completed: Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None = None` on both `simulate_graph_by_resource_type_async` and `_process_simulate_graph_by_resource_type_async` — this exact parameter name and type is what `helix.pipelines` wires up (see the companion plan, Task 3).

- [ ] **Step 1: Write the failing test**

This repo has no fixture-based FHIR client mocking. The established pattern (from
`helix_fhir_client_sdk/graph/test/test_simulate_graph_processor_mixin.py`, same
directory) is a `TestGraphProcessor(FhirClient)` subclass, a `get_graph_processor()`
helper, and `aioresponses()` for HTTP-level mocking. Mirror it exactly:

```python
from typing import Any

import pytest
from aioresponses import aioresponses

from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)
from helix_fhir_client_sdk.graph.simulated_graph_processor_mixin import (
    SimulatedGraphProcessorMixin,
)
from helix_fhir_client_sdk.graph.test.test_simulate_graph_processor_mixin import (
    get_graph_processor,
)

TWO_LINK_GRAPH: dict[str, Any] = {
    "id": "1",
    "name": "Test Graph",
    "resourceType": "GraphDefinition",
    "start": "Patient",
    "link": [
        {"target": [{"type": "AllergyIntolerance", "params": "patient={ref}"}]},
        {"target": [{"type": "CarePlan", "params": "patient={ref}"}]},
    ],
}


def mock_two_link_graph_responses(m: aioresponses) -> None:
    m.get(
        "http://example.com/fhir/Patient/1",
        payload={"resourceType": "Patient", "id": "1"},
    )
    m.get(
        "http://example.com/fhir/AllergyIntolerance?patient=1",
        payload={"resourceType": "AllergyIntolerance", "id": "1"},
    )
    m.get(
        "http://example.com/fhir/CarePlan?patient=1",
        payload={"resourceType": "CarePlan", "id": "1"},
    )


@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_once_per_link() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    events: list[ResourceTypeCompletionEvent] = []

    async def capture(event: ResourceTypeCompletionEvent) -> None:
        events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_resource_type_completed=capture,
            )
        ]

    assert len(responses) == 3  # Patient, AllergyIntolerance, CarePlan

    # one event for the start resource (Patient) + one per link
    assert len(events) == 3
    assert events[0].resource_types == ["Patient"]
    assert events[0].graph_depth == 0
    assert {t for e in events[1:] for t in e.resource_types} == {
        "AllergyIntolerance",
        "CarePlan",
    }
    assert all(e.graph_depth == 0 for e in events[1:])


@pytest.mark.asyncio
async def test_on_resource_type_completed_defaults_to_none_is_noop() -> None:
    # No callback passed — must behave exactly as before (regression guard for
    # the "zero behavior change for existing callers" constraint).
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
            )
        ]

    assert len(responses) == 3
```

`get_graph_processor` is module-private (no `__all__` restriction, but not
re-exported) — importing it from the sibling test module is consistent with how
this repo already shares test helpers across files in the same `test/` package;
if that import proves awkward in practice, duplicating the ~6-line helper locally
is also fine per this repo's "prefer duplication over the wrong abstraction" norm.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v`
Expected: FAIL with `TypeError: simulate_graph_by_resource_type_async() got an unexpected keyword argument 'on_resource_type_completed'`

- [ ] **Step 3: Implement**

Add the import at the top of `simulated_graph_processor_mixin.py`:

```python
from collections.abc import Awaitable, Callable

from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)
```

Add the parameter to `simulate_graph_by_resource_type_async` (public method, currently ends at line 1310 `compare_hash: bool = True,`):

```python
    async def simulate_graph_by_resource_type_async(
        self,
        *,
        id_: list[str] | str,
        graph_json: dict[str, Any],
        contained: bool,
        separate_bundle_resources: bool = False,
        restrict_to_scope: str | None = None,
        restrict_to_resources: list[str] | None = None,
        restrict_to_capability_statement: str | None = None,
        retrieve_and_restrict_to_capability_statement: bool | None = None,
        ifModifiedSince: datetime | None = None,
        eTag: str | None = None,
        request_size: int | None = 1,
        max_concurrent_tasks: int | None = 1,
        sort_resources: bool | None = False,
        add_cached_bundles_to_result: bool = True,
        input_cache: RequestCache | None = None,
        compare_hash: bool = True,
        on_resource_type_completed: (
            Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None
        ) = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
```

Also add a matching `:param on_resource_type_completed:` line to this method's
docstring — every other parameter has one (lines 1320-1336 of the current file),
so leaving this one undocumented breaks that convention. E.g.:

```
:param on_resource_type_completed: Optional async callback invoked once the start
                                     resource has been yielded, and again each time
                                     one graph link's resources have been fully
                                     yielded. Fires with a ResourceTypeCompletionEvent.
                                     Defaults to None (no-op, zero behavior change).
```

and pass it through in the call to `_process_simulate_graph_by_resource_type_async` (currently ends `compare_hash=compare_hash,` around line 1364):

```python
            compare_hash=compare_hash,
            on_resource_type_completed=on_resource_type_completed,
        ):
            yield r
```

Add the same parameter to `_process_simulate_graph_by_resource_type_async`'s signature (mirrors the public method's list, ending `compare_hash: bool = True,` around line 1391):

```python
        compare_hash: bool = True,
        on_resource_type_completed: (
            Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None
        ) = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
```

Fire it for the start resource, right after `yield parent_response` (currently line 1452):

```python
            # Yield the start resource (Patient) first
            parent_response.url = url or parent_response.url
            yield parent_response

            if on_resource_type_completed:
                await on_resource_type_completed(
                    ResourceTypeCompletionEvent(
                        resource_types=[start],
                        resource_count=parent_response_resource_count,
                        graph_depth=0,
                    )
                )
```

Fire it once per row, inside the outer `while` loop. Replace the current body (lines ~1461-1491):

```python
            graph_depth = 0
            while len(parent_link_map):
                new_parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []

                for links, current_parent_bundle_entries in parent_link_map:
                    link_responses: list[FhirGetResponse]
                    async for link_responses in AsyncParallelProcessor(
                        name="process_link_async_parallel_function",
                        max_concurrent_tasks=max_concurrent_tasks,
                    ).process_rows_in_parallel(
                        rows=links,
                        process_row_fn=self.process_link_async_parallel_function,
                        parameters=GraphLinkParameters(
                            parent_bundle_entries=current_parent_bundle_entries,
                            logger=logger,
                            cache=cache,
                            scope_parser=scope_parser,
                            max_concurrent_tasks=max_concurrent_tasks,
                        ),
                        log_level=self._log_level,
                        parent_link_map=new_parent_link_map,
                        request_size=request_size,
                        id_search_unsupported_resources=id_search_unsupported_resources,
                        add_cached_bundles_to_result=add_cached_bundles_to_result,
                        ifModifiedSince=ifModifiedSince,
                    ):
                        # Yield each link's responses individually instead of accumulating
                        for link_response in link_responses:
                            link_response.url = url or link_response.url
                            yield link_response

                        if on_resource_type_completed and link_responses:
                            resource_types = sorted(
                                {
                                    r.resource_type
                                    for r in link_responses
                                    if r.resource_type
                                }
                            )
                            if resource_types:
                                await on_resource_type_completed(
                                    ResourceTypeCompletionEvent(
                                        resource_types=resource_types,
                                        resource_count=sum(
                                            r.get_resource_count()
                                            for r in link_responses
                                        ),
                                        graph_depth=graph_depth,
                                    )
                                )

                parent_link_map = new_parent_link_map
                graph_depth += 1
```

Note two things:
1. The event fires *after* the `for link_response in link_responses: yield link_response` loop for that row — the caller has already received every resource for this link by the time the event arrives, satisfying "fully retrieved" (not "about to start").
2. `graph_depth += 1` is deliberately placed *after* `parent_link_map = new_parent_link_map`, not at the top of the `while` body. This makes the first pass (links directly off the start resource) fire with `graph_depth=0`, matching Task 1's `ResourceTypeCompletionEvent.graph_depth` docstring ("0 for links directly off the start resource") and its test assertions. Incrementing at the top of the loop instead — as an earlier draft of this plan did — would make first-level links fire at depth 1, contradicting Task 1's own test.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v`
Expected: PASS

- [ ] **Step 5: Run the full existing test suite for this module to confirm no regression**

Run: `pytest helix_fhir_client_sdk/graph/test/ -v -k "simulate_graph"`
Expected: All pre-existing tests for `simulate_graph_async` and `simulate_graph_by_resource_type_async` still PASS unchanged (they don't pass `on_resource_type_completed`, exercising the default-`None` no-op path).

- [ ] **Step 6: Commit**

```bash
git add helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "DCON-4509 add on_resource_type_completed callback to simulate_graph_by_resource_type_async"
```

---

## Task 3: Verify behavior under `max_concurrent_tasks > 1` (documented limitation, not a fix)

**Files:**
- Test: same file as Task 2.

This task exists because the whole reason this hook is more valuable than the status quo is that it doesn't silently break if a future caller sets `max_concurrent_tasks > 1`. Verify — don't try to "fix" interleaving here, since `AsyncParallelProcessor.process_rows_in_parallel` already yields one row's *complete* result per row (see its implementation, `helix_fhir_client_sdk/utilities/async_parallel_processor/v1/async_parallel_processor.py`) even when running concurrently; each `link_responses` list is still a fully-drained result for its own row regardless of concurrency, so the event Task 2 added is correct as-is. This step is a regression test proving that claim, not new code.

- [ ] **Step 1: Write the test**

Reuse the `TWO_LINK_GRAPH` graph and `mock_two_link_graph_responses` helper from
Task 2's test module (same file):

```python
@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_correctly_at_concurrency_2() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=2)

    events: list[ResourceTypeCompletionEvent] = []

    async def capture(event: ResourceTypeCompletionEvent) -> None:
        events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=2,
            on_resource_type_completed=capture,
        ):
            pass

    # Regardless of which of the two links finishes first, each event's
    # resource_types must be internally consistent (no mixing of two links'
    # resource types into one event) and resource_count must match the sum of
    # that link's own chunks.
    non_start_events = [e for e in events if e.resource_types != ["Patient"]]
    all_reported_types = [t for e in non_start_events for t in e.resource_types]
    assert sorted(all_reported_types) == sorted(["AllergyIntolerance", "CarePlan"])
```

- [ ] **Step 2: Run and confirm it passes without further code changes**

Run: `pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v -k concurrency`
Expected: PASS. If it fails, that's a real bug in `AsyncParallelProcessor` ordering assumptions — stop and re-examine `process_rows_in_parallel`'s semaphore-based branch (the `max_concurrent_tasks != 1` path) before proceeding; do not paper over it by forcing `max_concurrent_tasks=1` in the event-firing code.

- [ ] **Step 3: Commit**

```bash
git add helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "DCON-4509 verify on_resource_type_completed stays correct under concurrent link processing"
```

---

## Task 4: `ResourceTypeStartedEvent`, `GraphRetrievalStartedEvent`, `GraphRetrievalCompletedEvent` data types, and amend `ResourceTypeCompletionEvent`

**Context:** Tasks 1-3 shipped `on_resource_type_completed` alone. This task adds the payload types for the remaining three callbacks in the full lifecycle (`on_resource_type_started`, `on_graph_retrieval_started`, `on_graph_retrieval_completed` — wired in Task 5), and amends the already-shipped `ResourceTypeCompletionEvent` to carry the URL(s) actually queried to produce it. Without this, a caller that shares one callback across multiple concurrent `simulate_graph_by_resource_type_async()` calls (e.g. one connection per patient, all funneling into one progress handler — the actual `helix.pipelines` use case) has no way to tell which call an event belongs to. A full request URL already encodes the patient/resource id as a path or query parameter (e.g. `http://example.com/fhir/AllergyIntolerance?patient=1`), so one `urls`/`url` field carries that correlation without a separate identifier field. This is an amendment to already-committed, already-reviewed code (commits `3288f6a`, `72438eb`) — not a rewrite; add the field, don't restructure the file.

**Design note — why "completed" events get a list of actual URLs but "started" events only get the base server URL:** `FhirGetResponse.url` already holds the exact URL that was queried, including params (`fhir_get_response.py:99`, `:param url: url that was being accessed`) — it's populated by the underlying HTTP fetch before the response object exists, so by the time a "completed" event fires, the real per-request URL(s) are sitting right there on the response(s) already yielded. There's a wrinkle: `simulated_graph_processor_mixin.py` currently overwrites each response's `.url` with the connection's base URL right before yielding it (`parent_response.url = url or parent_response.url`, similarly for `link_response.url`) — this is existing, pre-this-plan behavior and out of scope to change, so capture each response's *original* `.url` into a local variable *before* that overwrite line runs, and use the captured value for the event; leave the overwrite itself untouched. "Started" events fire before any HTTP request for that resource type has even been constructed — the specific query parameters (which come from substituting the parent bundle's actual resource references into the link's `target.params` template, e.g. `patient={ref}`) aren't known yet at that point, so a "started" event can only carry the base connection URL, not the full query URL. Document this asymmetry in both dataclasses' docstrings so it isn't mistaken for an oversight.

**Files:**
- Modify: `helix_fhir_client_sdk/graph/resource_type_completion_event.py` — add two fields.
- Modify: `helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py` — update both existing test's construction calls to pass the two new fields (they have no default, so omitting them is a `TypeError`).
- Create: `helix_fhir_client_sdk/graph/resource_type_started_event.py` + test `helix_fhir_client_sdk/graph/test/test_resource_type_started_event.py`.
- Create: `helix_fhir_client_sdk/graph/graph_retrieval_started_event.py` + test `helix_fhir_client_sdk/graph/test/test_graph_retrieval_started_event.py`.
- Create: `helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py` + test `helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py`.

These four dataclasses are the same small, independent shape (plain `@dataclass(slots=True)` data carriers, no logic) — implement and test all four (one amendment + three new) in a single dispatch rather than four separate task loops.

**Interfaces:**
- `ResourceTypeCompletionEvent` (amended) fields become: `resource_types: list[str]`, `resource_count: int`, `graph_depth: int`, `urls: list[str]` (the actual URL(s) queried to produce this event, params included — one per `FhirGetResponse` chunk, since a link can yield more than one).
- `ResourceTypeStartedEvent` fields: `resource_types: list[str]`, `graph_depth: int`, `url: str` (the connection's base FHIR server URL — the specific query isn't constructed yet at this point; see the design note above).
- `GraphRetrievalStartedEvent` fields: `start_resource_type: str`, `url: str` (same base-URL caveat as above).
- `GraphRetrievalCompletedEvent` fields: `resource_types: list[str]`, `total_resource_count: int`, `max_graph_depth: int`, `urls: list[str]` (union of every actual URL queried across the whole traversal).
- All four consumed by Task 5.

- [ ] **Step 1: Write the failing tests**

Update the two existing tests in `helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py` to pass the two new required fields:

```python
from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)


def test_resource_type_completion_event_construction() -> None:
    event = ResourceTypeCompletionEvent(
        resource_types=["Condition"],
        resource_count=12,
        graph_depth=1,
        urls=["https://example.com/fhir/Condition?patient=123"],
    )
    assert event.resource_types == ["Condition"]
    assert event.resource_count == 12
    assert event.graph_depth == 1
    assert event.urls == ["https://example.com/fhir/Condition?patient=123"]


def test_resource_type_completion_event_multiple_types() -> None:
    # A single GraphDefinition link's `target` array can name more than one type
    # (e.g. a link with both AllergyIntolerance and CarePlan targets), so this
    # must accept more than one resource type — and more than one queried URL —
    # per event.
    event = ResourceTypeCompletionEvent(
        resource_types=["AllergyIntolerance", "CarePlan"],
        resource_count=5,
        graph_depth=0,
        urls=[
            "https://example.com/fhir/AllergyIntolerance?patient=123",
            "https://example.com/fhir/CarePlan?patient=123",
        ],
    )
    assert len(event.resource_types) == 2
    assert len(event.urls) == 2
```

Write the three new test files, one dataclass each:

```python
# helix_fhir_client_sdk/graph/test/test_resource_type_started_event.py
from helix_fhir_client_sdk.graph.resource_type_started_event import (
    ResourceTypeStartedEvent,
)


def test_resource_type_started_event_construction() -> None:
    event = ResourceTypeStartedEvent(
        resource_types=["Condition"],
        graph_depth=1,
        url="https://example.com/fhir",
    )
    assert event.resource_types == ["Condition"]
    assert event.graph_depth == 1
    assert event.url == "https://example.com/fhir"
```

```python
# helix_fhir_client_sdk/graph/test/test_graph_retrieval_started_event.py
from helix_fhir_client_sdk.graph.graph_retrieval_started_event import (
    GraphRetrievalStartedEvent,
)


def test_graph_retrieval_started_event_construction() -> None:
    event = GraphRetrievalStartedEvent(
        start_resource_type="Patient",
        url="https://example.com/fhir",
    )
    assert event.start_resource_type == "Patient"
    assert event.url == "https://example.com/fhir"
```

```python
# helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py
from helix_fhir_client_sdk.graph.graph_retrieval_completed_event import (
    GraphRetrievalCompletedEvent,
)


def test_graph_retrieval_completed_event_construction() -> None:
    event = GraphRetrievalCompletedEvent(
        resource_types=["Patient", "AllergyIntolerance", "CarePlan"],
        total_resource_count=3,
        max_graph_depth=0,
        urls=[
            "https://example.com/fhir/Patient/123",
            "https://example.com/fhir/AllergyIntolerance?patient=123",
            "https://example.com/fhir/CarePlan?patient=123",
        ],
    )
    assert event.resource_types == ["Patient", "AllergyIntolerance", "CarePlan"]
    assert event.total_resource_count == 3
    assert event.max_graph_depth == 0
    assert len(event.urls) == 3


def test_graph_retrieval_completed_event_zero_results() -> None:
    # Fires even when the start resource itself returned zero results —
    # callers need a definitive "done" signal either way.
    event = GraphRetrievalCompletedEvent(
        resource_types=[],
        total_resource_count=0,
        max_graph_depth=0,
        urls=["https://example.com/fhir/Patient/123"],
    )
    assert event.resource_types == []
    assert event.total_resource_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py helix_fhir_client_sdk/graph/test/test_resource_type_started_event.py helix_fhir_client_sdk/graph/test/test_graph_retrieval_started_event.py helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py -v`
Expected: the completion-event tests FAIL with `TypeError: ResourceTypeCompletionEvent.__init__() got an unexpected keyword argument 'urls'`; the three new-file tests FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Amend `helix_fhir_client_sdk/graph/resource_type_completion_event.py` — add one field at the end:

```python
    urls: list[str]
    """The actual URL(s) that were queried to produce this event's
    resources — one per FhirGetResponse chunk that contributed to it
    (usually one, occasionally more if the link had multiple targets or the
    response was paginated), params included (e.g.
    "https://example.com/fhir/AllergyIntolerance?patient=123"). Lets a
    callback shared across multiple concurrent
    simulate_graph_by_resource_type_async() calls tell which
    server/patient/call this event belongs to, since the patient/resource id
    is already embedded in the URL as a path or query parameter."""
```

Create `helix_fhir_client_sdk/graph/resource_type_started_event.py`:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class ResourceTypeStartedEvent:
    """
    Emitted by simulate_graph_by_resource_type_async() right before it begins
    retrieving one GraphDefinition link's resource type(s), or the start
    resource itself. Fires once per link (mirroring
    ResourceTypeCompletionEvent), before any HTTP request for that link has
    completed.
    """

    resource_types: list[str]
    """Resource type(s) about to be retrieved, taken from the graph
    definition's declared target types for this link (or [start] for the
    start resource) — not yet known-actual, since nothing has been fetched
    yet. Contrast with ResourceTypeCompletionEvent.resource_types, which
    reflects what was actually returned."""

    graph_depth: int
    """Same semantics as ResourceTypeCompletionEvent.graph_depth: 0 for links
    directly off the start resource, incremented once per level of
    target.link nesting."""

    url: str
    """The connection's base FHIR server URL (e.g. "https://example.com/fhir").
    Unlike ResourceTypeCompletionEvent.urls, this is NOT the full query URL
    with params — the specific request for this resource type hasn't been
    constructed yet when this event fires, since its query parameters come
    from substituting the parent bundle's actual resource references into
    the link's target.params template, which happens deeper in the request
    pipeline than this event's firing point."""
```

Create `helix_fhir_client_sdk/graph/graph_retrieval_started_event.py`:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class GraphRetrievalStartedEvent:
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(), before
    the start resource is fetched — the first thing the method does. Useful
    for "connecting..." progress UI.
    """

    start_resource_type: str
    """The graph definition's start resource type (e.g. "Patient")."""

    url: str
    """The connection's base FHIR server URL. Not the full query URL with
    params — see ResourceTypeStartedEvent.url's docstring for why."""
```

Create `helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py`:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class GraphRetrievalCompletedEvent:
    """
    Emitted exactly once by simulate_graph_by_resource_type_async(), after
    every resource in the graph has been yielded — the last thing the method
    does before returning (including the early-return path where the start
    resource itself returned zero results). Useful for "done" progress UI.
    """

    resource_types: list[str]
    """Distinct resource type(s) actually retrieved across the whole graph
    traversal (start resource + every link, every depth), sorted. Empty if
    the start resource itself returned zero results."""

    total_resource_count: int
    """Sum of get_resource_count() across every FhirGetResponse yielded
    during this call, including the start resource. 0 if the start resource
    returned zero results."""

    max_graph_depth: int
    """The deepest graph_depth value at which any link actually had
    resources to process (0 if only the start resource was retrieved, or if
    the start resource returned zero results)."""

    urls: list[str]
    """Union of every actual URL queried across the whole graph traversal
    (start resource + every link, every depth), params included. Contains
    at least the start resource's URL even if it returned zero results — a
    request was still made, it just came back empty — whereas
    resource_types is empty in that case, since nothing was actually
    retrieved. This event always fires exactly once, empty-result case
    included, since callers need a definitive "done" signal either way."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run the same command as Step 2. Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add helix_fhir_client_sdk/graph/resource_type_completion_event.py helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py helix_fhir_client_sdk/graph/resource_type_started_event.py helix_fhir_client_sdk/graph/test/test_resource_type_started_event.py helix_fhir_client_sdk/graph/graph_retrieval_started_event.py helix_fhir_client_sdk/graph/test/test_graph_retrieval_started_event.py helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py helix_fhir_client_sdk/graph/test/test_graph_retrieval_completed_event.py
git commit -m "DCON-4509 add urls field to ResourceTypeCompletionEvent; add started/graph-lifecycle event types"
```

---

## Task 5: Thread `on_resource_type_started`, `on_graph_retrieval_started`, `on_graph_retrieval_completed` through `simulate_graph_by_resource_type_async`

**Context:** This is the wiring task for the three new callbacks, and it also amends Task 2's two existing `ResourceTypeCompletionEvent(...)` construction call sites to pass the two new fields added in Task 4 — those call sites are otherwise unchanged.

**Files:**
- Modify: `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py` (`simulate_graph_by_resource_type_async`, `_process_simulate_graph_by_resource_type_async`, `process_link_async_parallel_function`).
- Modify: `helix_fhir_client_sdk/graph/graph_link_parameters.py` — add fields so `on_resource_type_started` can reach `process_link_async_parallel_function` (which runs as its own per-row task, unlike `on_resource_type_completed` which fires from the single-threaded outer generator loop).
- Modify: `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py` — extend with new tests for the full event sequence. Do not rename this file even though its scope now covers more than "completion" — renaming an already-committed test file is unnecessary churn.

**Interfaces:**
- Consumes: `ResourceTypeStartedEvent`, `GraphRetrievalStartedEvent`, `GraphRetrievalCompletedEvent` from Task 4.
- Produces: three new keyword-only parameters on both `simulate_graph_by_resource_type_async` and `_process_simulate_graph_by_resource_type_async`:
  - `on_resource_type_started: Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None = None`
  - `on_graph_retrieval_started: Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None = None`
  - `on_graph_retrieval_completed: Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None = None`
- `GraphLinkParameters` gains three new fields, all with defaults so the unrelated `simulate_graph_async()` call site at `simulated_graph_processor_mixin.py:223` needs no change:
  - `on_resource_type_started: Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None = None`
  - `graph_depth: int = 0`
  - `url: str = ""` (the connection's base FHIR server URL, for `ResourceTypeStartedEvent.url`).

- [ ] **Step 1: Write the failing tests**

Append to the existing `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py` (reuse its `TWO_LINK_GRAPH`, `mock_two_link_graph_responses`, `get_graph_processor` — do not redefine them):

```python
from helix_fhir_client_sdk.graph.graph_retrieval_completed_event import (
    GraphRetrievalCompletedEvent,
)
from helix_fhir_client_sdk.graph.graph_retrieval_started_event import (
    GraphRetrievalStartedEvent,
)
from helix_fhir_client_sdk.graph.resource_type_started_event import (
    ResourceTypeStartedEvent,
)


@pytest.mark.asyncio
async def test_full_event_lifecycle_fires_in_order_at_concurrency_1() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    started_events: list[ResourceTypeStartedEvent] = []
    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_started_events: list[GraphRetrievalStartedEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_started(event: GraphRetrievalStartedEvent) -> None:
        graph_started_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_resource_type_started=on_started,
                on_resource_type_completed=on_completed,
                on_graph_retrieval_started=on_graph_started,
                on_graph_retrieval_completed=on_graph_completed,
            )
        ]

    assert len(responses) == 3  # Patient, AllergyIntolerance, CarePlan

    # exactly one graph-level bookend event each
    assert len(graph_started_events) == 1
    assert graph_started_events[0].start_resource_type == "Patient"
    assert graph_started_events[0].url == "http://example.com/fhir"

    assert len(graph_completed_events) == 1
    assert sorted(graph_completed_events[0].resource_types) == sorted(
        ["Patient", "AllergyIntolerance", "CarePlan"]
    )
    assert graph_completed_events[0].total_resource_count == 3
    assert graph_completed_events[0].max_graph_depth == 0
    assert sorted(graph_completed_events[0].urls) == sorted(
        [
            "http://example.com/fhir/Patient/1",
            "http://example.com/fhir/AllergyIntolerance?patient=1",
            "http://example.com/fhir/CarePlan?patient=1",
        ]
    )

    # one started + one completed per resource type (start resource + 2 links)
    assert len(started_events) == 3
    assert len(completed_events) == 3
    assert started_events[0].resource_types == ["Patient"]
    assert started_events[0].url == "http://example.com/fhir"
    assert completed_events[0].resource_types == ["Patient"]
    assert completed_events[0].urls == ["http://example.com/fhir/Patient/1"]

    # at max_concurrent_tasks=1, ordering is fully deterministic: graph_started
    # fires before anything else, graph_completed fires after everything else,
    # and each resource type's started event fires immediately before its own
    # completed event (not interleaved with any other resource type's events).
    started_types_in_order = [e.resource_types[0] for e in started_events]
    completed_types_in_order = [e.resource_types[0] for e in completed_events]
    assert started_types_in_order == completed_types_in_order


@pytest.mark.asyncio
async def test_graph_retrieval_completed_fires_on_zero_results() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        m.get(
            "http://example.com/fhir/Patient/1",
            payload={"resourceType": "Bundle", "entry": []},
        )

        responses = [
            r
            async for r in graph_processor.simulate_graph_by_resource_type_async(
                id_="1",
                graph_json=TWO_LINK_GRAPH,
                contained=False,
                max_concurrent_tasks=1,
                on_graph_retrieval_completed=on_graph_completed,
            )
        ]

    assert len(responses) == 1  # just the empty start-resource response
    assert len(graph_completed_events) == 1
    assert graph_completed_events[0].resource_types == []
    assert graph_completed_events[0].total_resource_count == 0
    assert graph_completed_events[0].max_graph_depth == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v -k "lifecycle or zero_results"`
Expected: FAIL with `TypeError: simulate_graph_by_resource_type_async() got an unexpected keyword argument 'on_resource_type_started'`.

- [ ] **Step 3: Implement**

Add imports at the top of `simulated_graph_processor_mixin.py`:

```python
from helix_fhir_client_sdk.graph.graph_retrieval_completed_event import (
    GraphRetrievalCompletedEvent,
)
from helix_fhir_client_sdk.graph.graph_retrieval_started_event import (
    GraphRetrievalStartedEvent,
)
from helix_fhir_client_sdk.graph.resource_type_started_event import (
    ResourceTypeStartedEvent,
)
```

Amend `helix_fhir_client_sdk/graph/graph_link_parameters.py` — add the import and the three new fields (all with defaults, so `simulated_graph_processor_mixin.py:223`'s existing `GraphLinkParameters(...)` construction for the unrelated `simulate_graph_async()` path needs no change):

```python
from collections.abc import Awaitable, Callable

from helix_fhir_client_sdk.graph.resource_type_started_event import (
    ResourceTypeStartedEvent,
)

# ... existing imports/fields unchanged ...

    on_resource_type_started: Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None = None
    """Optional callback fired once per row (GraphDefinitionLink) right
    before that link's resources begin retrieving. None for callers that
    don't use simulate_graph_by_resource_type_async's per-resource-type
    hooks (e.g. simulate_graph_async)."""

    graph_depth: int = 0
    """The graph_depth of the current outer-loop pass this row belongs to.
    Only meaningful together with on_resource_type_started; unused
    otherwise."""

    url: str = ""
    """The connection's base FHIR server URL for this call, passed straight
    through to ResourceTypeStartedEvent.url (see that dataclass's docstring
    for why it's the base URL and not the full query URL). Only meaningful
    together with on_resource_type_started; unused otherwise."""
```

Add the started-event firing to `process_link_async_parallel_function`, right after the existing `assert parameters, "Processing parameters must be provided"` line and before the existing debug-logging block:

```python
        # Validate input parameters
        assert parameters, "Processing parameters must be provided"

        if parameters.on_resource_type_started and row.target:
            started_resource_types = sorted({target.type_ for target in row.target if target.type_})
            if started_resource_types:
                await parameters.on_resource_type_started(
                    ResourceTypeStartedEvent(
                        resource_types=started_resource_types,
                        graph_depth=parameters.graph_depth,
                        url=parameters.url,
                    )
                )
```

Add the three new parameters to `simulate_graph_by_resource_type_async`'s signature, right after `on_resource_type_completed`:

```python
        on_resource_type_completed: (
            Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None
        ) = None,
        on_resource_type_started: (
            Callable[[ResourceTypeStartedEvent], Awaitable[None]] | None
        ) = None,
        on_graph_retrieval_started: (
            Callable[[GraphRetrievalStartedEvent], Awaitable[None]] | None
        ) = None,
        on_graph_retrieval_completed: (
            Callable[[GraphRetrievalCompletedEvent], Awaitable[None]] | None
        ) = None,
    ) -> AsyncGenerator[FhirGetResponse, None]:
```

Add matching `:param:` docstring lines (same pattern as the existing `:param on_resource_type_completed:` line added in Task 2), and pass all three through in the call to `_process_simulate_graph_by_resource_type_async`:

```python
            on_resource_type_completed=on_resource_type_completed,
            on_resource_type_started=on_resource_type_started,
            on_graph_retrieval_started=on_graph_retrieval_started,
            on_graph_retrieval_completed=on_graph_retrieval_completed,
        ):
            yield r
```

Add the same three parameters to `_process_simulate_graph_by_resource_type_async`'s signature, right after its existing `on_resource_type_completed` param.

Replace the body from `if not isinstance(id_, list):` through the end of the function with:

```python
        if not isinstance(id_, list):
            id_ = id_.split(",")

        base_url_value: str = url or ""

        id_search_unsupported_resources: list[str] = []
        cache: RequestCache = input_cache if input_cache is not None else RequestCache()
        async with cache:
            start: str = graph_definition.start

            if on_graph_retrieval_started:
                await on_graph_retrieval_started(
                    GraphRetrievalStartedEvent(
                        start_resource_type=start,
                        url=base_url_value,
                    )
                )

            if on_resource_type_started:
                await on_resource_type_started(
                    ResourceTypeStartedEvent(
                        resource_types=[start],
                        graph_depth=0,
                        url=base_url_value,
                    )
                )

            parent_response: FhirGetResponse
            cache_hits: int
            parent_response, cache_hits = await self._get_resources_by_parameters_async(
                resource_type=start,
                id_=id_,
                cache=cache,
                scope_parser=scope_parser,
                logger=logger,
                id_search_unsupported_resources=id_search_unsupported_resources,
                add_cached_bundles_to_result=add_cached_bundles_to_result,
                compare_hash=compare_hash,
            )
            # Capture the actual queried URL (with params) before the existing
            # line below overwrites it with the connection's base URL —
            # that overwrite is pre-existing behavior, out of scope to change.
            parent_queried_url: str = parent_response.url

            parent_response_resource_count = parent_response.get_resource_count()
            if parent_response_resource_count == 0:
                yield parent_response
                if on_graph_retrieval_completed:
                    await on_graph_retrieval_completed(
                        GraphRetrievalCompletedEvent(
                            resource_types=[],
                            total_resource_count=0,
                            max_graph_depth=0,
                            urls=[parent_queried_url],
                        )
                    )
                return

            if logger:
                logger.info(
                    f"FhirClient.simulate_graph_by_resource_type_async() "
                    f"got parent resources: {parent_response_resource_count} "
                    f"cached:{cache_hits}"
                )

            # Yield the start resource (Patient) first
            parent_response.url = url or parent_response.url
            yield parent_response

            if on_resource_type_completed:
                await on_resource_type_completed(
                    ResourceTypeCompletionEvent(
                        resource_types=[start],
                        resource_count=parent_response_resource_count,
                        graph_depth=0,
                        urls=[parent_queried_url],
                    )
                )

            all_resource_types: set[str] = {start}
            total_resource_count: int = parent_response_resource_count
            max_graph_depth: int = 0
            all_urls: set[str] = {parent_queried_url}

            parent_bundle_entries: FhirBundleEntryList = parent_response.get_bundle_entries()

            parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []
            if graph_definition.link and parent_bundle_entries:
                parent_link_map.append((graph_definition.link, parent_bundle_entries))

            # Process graph links one at a time and yield each link's response
            graph_depth = 0
            while len(parent_link_map):
                new_parent_link_map: list[tuple[list[GraphDefinitionLink], FhirBundleEntryList]] = []

                for links, current_parent_bundle_entries in parent_link_map:
                    link_responses: list[FhirGetResponse]
                    async for link_responses in AsyncParallelProcessor(
                        name="process_link_async_parallel_function",
                        max_concurrent_tasks=max_concurrent_tasks,
                    ).process_rows_in_parallel(
                        rows=links,
                        process_row_fn=self.process_link_async_parallel_function,
                        parameters=GraphLinkParameters(
                            parent_bundle_entries=current_parent_bundle_entries,
                            logger=logger,
                            cache=cache,
                            scope_parser=scope_parser,
                            max_concurrent_tasks=max_concurrent_tasks,
                            on_resource_type_started=on_resource_type_started,
                            graph_depth=graph_depth,
                            url=base_url_value,
                        ),
                        log_level=self._log_level,
                        parent_link_map=new_parent_link_map,
                        request_size=request_size,
                        id_search_unsupported_resources=id_search_unsupported_resources,
                        add_cached_bundles_to_result=add_cached_bundles_to_result,
                        ifModifiedSince=ifModifiedSince,
                    ):
                        # Capture each response's actual queried URL before the
                        # existing loop below overwrites it with the base URL.
                        link_queried_urls = [r.url for r in link_responses]

                        # Yield each link's responses individually instead of accumulating
                        for link_response in link_responses:
                            link_response.url = url or link_response.url
                            yield link_response

                        if link_responses and (on_resource_type_completed or on_graph_retrieval_completed):
                            resource_types = sorted({r.resource_type for r in link_responses if r.resource_type})
                            if resource_types:
                                resource_count_for_link = sum(r.get_resource_count() for r in link_responses)
                                all_resource_types.update(resource_types)
                                total_resource_count += resource_count_for_link
                                max_graph_depth = graph_depth
                                all_urls.update(link_queried_urls)
                                if on_resource_type_completed:
                                    await on_resource_type_completed(
                                        ResourceTypeCompletionEvent(
                                            resource_types=resource_types,
                                            resource_count=resource_count_for_link,
                                            graph_depth=graph_depth,
                                            urls=link_queried_urls,
                                        )
                                    )

                parent_link_map = new_parent_link_map
                graph_depth += 1

            if logger:
                logger.info(
                    f"Request Cache for: id_={id_}, "
                    f"start={graph_definition.start}, "
                    f"hits: {cache.cache_hits}, "
                    f"misses: {cache.cache_misses}"
                )

            if on_graph_retrieval_completed:
                await on_graph_retrieval_completed(
                    GraphRetrievalCompletedEvent(
                        resource_types=sorted(all_resource_types),
                        total_resource_count=total_resource_count,
                        max_graph_depth=max_graph_depth,
                        urls=sorted(all_urls),
                    )
                )
```

Note two things:
1. The `if link_responses and (on_resource_type_completed or on_graph_retrieval_completed):` guard replaces Task 2's narrower `if on_resource_type_completed and link_responses:` guard, because the aggregation now feeds both the per-type callback AND the whole-graph summary — but it's still a no-op (no new computation at all) when neither callback is registered, preserving the "zero behavior/cost change for existing callers" constraint. `resource_count_for_link` is computed once and reused for both `total_resource_count` and the per-type event, removing the duplicate `sum()` call Task 2 had.
2. `parent_queried_url`/`link_queried_urls` are captured *before* the pre-existing `parent_response.url = url or parent_response.url` / `link_response.url = url or link_response.url` lines run — those lines are untouched, so every existing consumer's `FhirGetResponse.url` still ends up exactly as it did before this task; only the new events see the pre-overwrite value.

- [ ] **Step 4: Run tests to verify they pass**

Run the Step 2 command, then the full completion-hook file:
`uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v`
Expected: all PASS, including the three pre-existing tests from Tasks 2-3 (they don't pass the three new parameters, exercising the default-`None` no-op path for all of them).

- [ ] **Step 5: Run the full existing test suite for this module to confirm no regression**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/ -v -k "simulate_graph"` and `uv run mypy helix_fhir_client_sdk/graph/`.

- [ ] **Step 6: Commit**

```bash
git add helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py helix_fhir_client_sdk/graph/graph_link_parameters.py helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "DCON-4509 add on_resource_type_started/on_graph_retrieval_started/on_graph_retrieval_completed callbacks"
```

---

## Task 6: Verify the new started/graph-lifecycle events under `max_concurrent_tasks > 1`

**Files:**
- Test: same file as Tasks 2, 3, and 5 (`helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py`).

Mirrors Task 3's spirit for the three new events. `on_resource_type_started` fires from inside `process_link_async_parallel_function` — a per-row task that can run truly concurrently with other rows' tasks when `max_concurrent_tasks > 1` — unlike `on_resource_type_completed`, which is serialized through the single-threaded outer generator loop. So the invariant to verify is narrower than "global order": for *each* resource type, its own `started` event must precede its own `completed` event (guaranteed, since `started` fires inside that row's task before any of that row's results are returned, and `completed` fires only after the outer loop receives that row's full result) — but *different* resource types' `started` events may arrive in either relative order under concurrency. The two whole-graph bookend events must each still fire exactly once, before/after everything else respectively, regardless of concurrency (guaranteed by their placement outside the concurrent-rows section entirely).

- [ ] **Step 1: Write the test**

Append to the same file, reusing `TWO_LINK_GRAPH`/`mock_two_link_graph_responses`:

```python
@pytest.mark.asyncio
async def test_full_event_lifecycle_stays_correct_at_concurrency_2() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=2)

    started_events: list[ResourceTypeStartedEvent] = []
    completed_events: list[ResourceTypeCompletionEvent] = []
    graph_started_events: list[GraphRetrievalStartedEvent] = []
    graph_completed_events: list[GraphRetrievalCompletedEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    async def on_graph_started(event: GraphRetrievalStartedEvent) -> None:
        graph_started_events.append(event)

    async def on_graph_completed(event: GraphRetrievalCompletedEvent) -> None:
        graph_completed_events.append(event)

    with aioresponses() as m:
        mock_two_link_graph_responses(m)

        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=2,
            on_resource_type_started=on_started,
            on_resource_type_completed=on_completed,
            on_graph_retrieval_started=on_graph_started,
            on_graph_retrieval_completed=on_graph_completed,
        ):
            pass

    # whole-graph bookends: exactly once each, regardless of concurrency
    assert len(graph_started_events) == 1
    assert len(graph_completed_events) == 1
    assert sorted(graph_completed_events[0].resource_types) == sorted(
        ["Patient", "AllergyIntolerance", "CarePlan"]
    )

    # per-type started/completed: one of each per resource type
    started_by_type = {e.resource_types[0]: i for i, e in enumerate(started_events)}
    completed_by_type = {e.resource_types[0]: i for i, e in enumerate(completed_events)}
    assert set(started_by_type) == {"Patient", "AllergyIntolerance", "CarePlan"}
    assert set(completed_by_type) == {"Patient", "AllergyIntolerance", "CarePlan"}

    # the narrower invariant that actually holds under concurrency: each type's
    # own started event precedes that same type's own completed event. Do NOT
    # assert a global order across different types here — that's the one thing
    # concurrency legitimately does not guarantee.
    for resource_type in ("Patient", "AllergyIntolerance", "CarePlan"):
        started_index = started_by_type[resource_type]
        completed_index = completed_by_type[resource_type]
        # started_events and completed_events are separate lists, so compare
        # via the index each event was appended at within its own list plus
        # the fact both lists are chronological — verify order using a single
        # merged timeline captured via a shared counter instead:
        assert started_index is not None and completed_index is not None
```

The commented-out-looking final loop above is intentionally incomplete — this is the one part of this task requiring judgment: a plain `list.index()` comparison across two *separate* lists (`started_events`, `completed_events`) cannot establish relative ordering between them. Implement it properly using a single shared timeline: have all four callbacks append `(kind, event)` tuples to one shared `timeline: list[tuple[str, str]]` list (`kind` being `"started"` or `"completed"`, second element the resource type or a marker for the graph-level events) instead of four separate lists, then assert that for each resource type, the first `"started"` entry for that type appears at a lower index than the first `"completed"` entry for that type. Rewrite the test around one shared timeline list rather than four separate ones — the four-separate-lists sketch above was this plan's first draft and doesn't actually verify the ordering it claims to; treat it as showing intent, not final code.

- [ ] **Step 2: Run and confirm it passes without further code changes**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py -v -k concurrency_2`
Expected: PASS. If the per-type started-before-completed invariant fails, that is a real bug (fix it in this task, unlike Task 3 — this invariant is actually load-bearing on this task's own code, not an inherited assumption from `AsyncParallelProcessor`).

- [ ] **Step 3: Commit**

```bash
git add helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "DCON-4509 verify started/graph-lifecycle events stay correct under concurrent link processing"
```

---

## Task 7: Coordinate the release with `helix.pipelines`

**Files:** none — no file changes in this task.

There is no `CHANGELOG.md` in this repo, and `VERSION` is not manually maintained:
`.github/workflows/python-publish.yml`'s "Set release tag in VERSION" step
overwrites the `VERSION` file from the GitHub release tag at publish time
(`on: release: types: [created]`), and `git log -p -- VERSION` shows it has never
been hand-edited since its initial `0.0.1` commit. Do not add a step to manually
edit or commit `VERSION` — CI derives it from the tag when a release is cut.

- [ ] **Step 1: Note the intended version bump in the PR description**

Since this is an additive, backward-compatible change, note in the PR description
(for whoever cuts the GitHub release) that it warrants a semver-minor bump, not a
patch — no file change needed on this branch.

- [ ] **Step 2: Coordinate the release with `helix.pipelines`**

The companion plan in `helix.pipelines` (`docs/superpowers/plans/2026-08-22-proa-per-resource-type-progress.md`, Task 1) pins this exact version once published. Do not merge that plan's Task 1 until this SDK version is actually released (published to whatever package index `helix.pipelines`' `Pipfile` resolves `helix-fhir-client-sdk` from — check `Pipfile` there for the source).

---

## Task 8: Final-review fixes (correlation key, always-fire `completed`, guaranteed terminal event)

**Context:** Tasks 1-7 shipped and passed a final whole-branch review. That review found the mechanical implementation sound (backward compatibility, URL-capture ordering, `graph_depth` threading, concurrency semantics all correct) but identified 5 Important, plan-level API-contract gaps and one real test gap, all pre-existing in the design Tasks 1-7 faithfully implemented — not implementer deviations:

1. **`on_resource_type_started` has no guaranteed `on_resource_type_completed` counterpart.** A link whose target(s) return zero results (very common — e.g. a `path`-based link like `Patient.generalPractitioner` when the patient has none) fires `started` but the `if resource_types:` guard suppresses `completed` entirely. Same gap for the start resource's own zero-result early-return path (`started(Patient)` fires, `completed(Patient)` never does). A progress UI built on this lifecycle shows "retrieving X..." forever.
2. **`urls` can be `[""]`.** `FhirGetResponse.url` is `""` on the scope-denied and fully-cached-with-no-HTTP-call paths through `_get_resources_by_parameters_async`, defeating the correlation purpose the field exists for.
3. **`GraphRetrievalCompletedEvent`'s "always fires exactly once" docstring is false.** Nothing fires it if an exception propagates from inside the traversal, or if the caller stops consuming the generator early (a completely normal thing to do with a streaming generator).
4. **`started`/`completed` have no stable correlation key.** They're paired only by resource-type string, which breaks for multi-target links with partial results, two different links declaring the same type at the same depth, and the documented "type recurs at a later depth" case.
5. **Two other docstrings assert things the code doesn't do**, one of them self-contradictory (`ResourceTypeCompletionEvent.resource_types`' parenthetical claims empty results "still fire" while the code suppresses them, and references an internal plan task number no external consumer can resolve).
6. **Real test gap:** nothing exercises `graph_depth > 0` — every test fixture is a flat, non-nested graph, so the second pass of the outer `while` loop (`simulated_graph_processor_mixin.py`'s traversal) is entirely unverified by any test in this feature.

This is the last task before the branch is done. There is no second fix-wave after this one — get it right in one pass.

**Files:**
- Modify: `helix_fhir_client_sdk/utilities/async_parallel_processor/v1/async_parallel_processor.py` — add an opt-in `yield_context` parameter (see below). This is a shared utility with exactly one other consumer in this repo (`simulate_graph_async()`'s call site at `simulated_graph_processor_mixin.py:~232`) — the change must be 100% inert for that call site.
- Create: `helix_fhir_client_sdk/utilities/async_parallel_processor/v1/test/test_async_parallel_processor.py` (this class currently has zero tests; follow this repo's `test/`-subpackage-next-to-source convention).
- Modify: `helix_fhir_client_sdk/graph/resource_type_started_event.py`, `helix_fhir_client_sdk/graph/resource_type_completion_event.py` — add `link_index: int` to both; fix the wrong docstring on the latter.
- Modify: `helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py` — fix the "always fires" / empty-`urls` docstring wording (the behavior fix below makes "always fires" true; the `urls`-can-be-empty wording needs correcting regardless).
- Modify: `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py` — the full fix described below.
- Modify: `helix_fhir_client_sdk/graph/test/test_resource_type_started_event.py`, `helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py` — add `link_index` to existing construction calls.
- Modify: `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py` — add the depth>0 test, and update existing assertions that construct/compare events to account for the new `link_index` field where relevant.

**Design decisions (already made — implement as specified, no further judgment calls needed on these five points):**

1. **Correlation key = `(graph_depth, link_index)`.** `link_index` is `-1` for the start resource (a sentinel — it isn't processed via `AsyncParallelProcessor`, so it has no natural index), and `AsyncParallelProcessor`'s existing `ParallelFunctionContext.task_index` for every link (already assigned via `enumerate(rows)` before dispatch — confirmed stable and deterministic regardless of completion order). `task_index` was already available to `process_link_async_parallel_function` (hence to `on_resource_type_started`'s firing site); it was NOT available to the outer generator loop that fires `on_resource_type_completed` — fixing that gap is the `AsyncParallelProcessor` change below.
2. **`AsyncParallelProcessor.process_rows_in_parallel` gains `yield_context: bool = False`.** When `False` (the default — `simulate_graph_async()`'s call site needs zero changes), yields bare `TOutput` exactly as today. When `True`, yields `tuple[ParallelFunctionContext, TOutput]` instead. Only `_process_simulate_graph_by_resource_type_async`'s call site passes `yield_context=True`.
3. **`on_resource_type_completed` fires once per row, unconditionally** (still only if a callback is registered) — no longer gated on `link_responses` being non-empty or containing a non-`None` `resource_type`. When nothing came back, it reports the link's *declared* target type(s) (looked up via `links[context.task_index].target`) with `resource_count=0`, so a caller that received `started` for this link always receives a matching `completed`. The whole-graph aggregation (`all_resource_types`/`total_resource_count`/`all_urls`) is unaffected by this fallback — it still only reflects resources *actually* retrieved, matching its existing docstring.
4. **`on_graph_retrieval_completed` fires from exactly one `try/finally` block wrapping the whole traversal**, not from three separate call sites (the current zero-result-return, post-loop, and — previously missing — exception/early-close paths). This makes the "always fires exactly once" docstring true for normal completion, the zero-result path, exceptions, and the caller breaking out of / closing the generator early (which Python's `async for` guarantees calls `aclose()`, running `finally` blocks). Document as a known, unavoidable limitation of async generators that a caller who lets the generator become unreachable *without* explicit `break`/`aclose()` may not observe this event — that's a general Python limitation, not something this fix can close.
5. **Empty-string URLs are filtered out** at the point of capture (`if r.url`), for both the parent response and every link response, before building any event's `urls` list.

**Interfaces:**
- `ResourceTypeStartedEvent` and `ResourceTypeCompletionEvent` both gain `link_index: int` (`-1` for the start resource, `context.task_index` for links).
- `AsyncParallelProcessor.process_rows_in_parallel` gains `yield_context: bool = False`.

- [ ] **Step 1: Write the failing tests**

Update the two dataclasses' existing tests to pass `link_index`:

```python
# helix_fhir_client_sdk/graph/test/test_resource_type_started_event.py — add to the existing construction call:
        link_index=-1,
# ...and assert:
    assert event.link_index == -1
```

```python
# helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py — add to BOTH existing construction calls:
        link_index=0,
# ...and assert:
    assert event.link_index == 0
```

Write a new test file for `AsyncParallelProcessor`, covering both branches (`max_concurrent_tasks=1` and `>1`) with `yield_context=True`, plus a regression test proving `yield_context=False` (the default) is byte-for-byte the existing behavior:

```python
# helix_fhir_client_sdk/utilities/async_parallel_processor/v1/test/test_async_parallel_processor.py
import pytest

from helix_fhir_client_sdk.utilities.async_parallel_processor.v1.async_parallel_processor import (
    AsyncParallelProcessor,
    ParallelFunctionContext,
)


async def double_it(
    *, context: ParallelFunctionContext, row: int, parameters: None, additional_parameters: dict | None
) -> int:
    return row * 2


@pytest.mark.asyncio
async def test_yield_context_false_is_default_and_unchanged() -> None:
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=1)
    results = [r async for r in processor.process_rows_in_parallel(rows=[1, 2, 3], process_row_fn=double_it, parameters=None)]
    assert results == [2, 4, 6]


@pytest.mark.asyncio
async def test_yield_context_true_sequential() -> None:
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=1)
    results = [
        (ctx.task_index, ctx.total_task_count, value)
        async for ctx, value in processor.process_rows_in_parallel(
            rows=[1, 2, 3], process_row_fn=double_it, parameters=None, yield_context=True
        )
    ]
    assert results == [(0, 3, 2), (1, 3, 4), (2, 3, 6)]


@pytest.mark.asyncio
async def test_yield_context_true_concurrent() -> None:
    processor = AsyncParallelProcessor(name="test", max_concurrent_tasks=2)
    results = [
        (ctx.task_index, value)
        async for ctx, value in processor.process_rows_in_parallel(
            rows=[1, 2, 3], process_row_fn=double_it, parameters=None, yield_context=True
        )
    ]
    # completion order isn't guaranteed under concurrency; task_index correctly
    # identifies which row each result belongs to regardless of arrival order
    assert sorted(results) == [(0, 2), (1, 4), (2, 6)]
```

Write the depth>0 test. Base the nested `target.link` JSON shape on the existing `test_graph_definition_with_nested_links` test in `helix_fhir_client_sdk/graph/test/test_simulate_graph_processor_mixin.py` (same repo, same nested-graph-definition parsing, just a different top-level method) — copy its exact `link`/`target`/nested-`link` JSON structure rather than guessing the shape `GraphDefinitionTarget.from_dict` expects. Add to `test_simulate_graph_by_resource_type_async_completion_hook.py`:

```python
@pytest.mark.asyncio
async def test_started_and_completed_events_fire_at_depth_1_for_nested_links() -> None:
    graph_processor: SimulatedGraphProcessorMixin = get_graph_processor(max_concurrent_requests=1)

    started_events: list[ResourceTypeStartedEvent] = []
    completed_events: list[ResourceTypeCompletionEvent] = []

    async def on_started(event: ResourceTypeStartedEvent) -> None:
        started_events.append(event)

    async def on_completed(event: ResourceTypeCompletionEvent) -> None:
        completed_events.append(event)

    # NESTED_GRAPH: Patient -> Encounter (depth 0) -> Practitioner (depth 1),
    # matching the target.link nesting shape from
    # test_graph_definition_with_nested_links in test_simulate_graph_processor_mixin.py.
    with aioresponses() as m:
        # mock Patient/1, Encounter?patient=1, and the nested Practitioner lookup
        # using the same URL patterns as test_graph_definition_with_nested_links
        ...
        async for _ in graph_processor.simulate_graph_by_resource_type_async(
            id_="1",
            graph_json=NESTED_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
            on_resource_type_started=on_started,
            on_resource_type_completed=on_completed,
        ):
            pass

    depth_1_started = [e for e in started_events if e.graph_depth == 1]
    depth_1_completed = [e for e in completed_events if e.graph_depth == 1]
    assert len(depth_1_started) == 1
    assert depth_1_started[0].resource_types == ["Practitioner"]
    assert len(depth_1_completed) == 1
    assert depth_1_completed[0].resource_types == ["Practitioner"]
```

The `...` above (mock setup, exact `NESTED_GRAPH` dict) is intentionally left for the implementer to fill in by copying `test_graph_definition_with_nested_links`'s fixture — don't guess the JSON shape.

- [ ] **Step 2: Run tests to verify they fail**

New/changed tests should fail: `link_index` tests with `TypeError` (missing kwarg), `AsyncParallelProcessor` tests with `TypeError: process_rows_in_parallel() got an unexpected keyword argument 'yield_context'`, the depth-1 test with an assertion failure (0 events at depth 1, since nothing fires past depth 0 yet in the fixture you're introducing — or a `KeyError`/parsing error if the nested JSON isn't wired up yet).

- [ ] **Step 3: Implement**

Amend `async_parallel_processor.py`:

```python
    async def process_rows_in_parallel[
        TInput,
        TOutput,
        TParameters: dict[str, Any] | object,
    ](
        self,
        *,
        rows: list[TInput],
        process_row_fn: ParallelFunction[TInput, TOutput, TParameters],
        parameters: TParameters | None,
        log_level: str | None = None,
        yield_context: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[TOutput, None]:
```

(Note: the return type annotation stays `AsyncGenerator[TOutput, None]` for simplicity/least-diff even though it's technically `AsyncGenerator[TOutput | tuple[ParallelFunctionContext, TOutput], None]` when `yield_context=True` — this mirrors how the method is already fully dynamic via `**kwargs`; if your type checker complains, use `# type: ignore[misc]` on the yield lines rather than restructuring the generic signature.)

Sequential branch:

```python
        if self.max_concurrent_tasks == 1:
            for i, row in enumerate(rows):
                context = ParallelFunctionContext(
                    name=self.name,
                    log_level=log_level,
                    task_index=i,
                    total_task_count=len(rows),
                )
                result = await process_row_fn(
                    context=context,
                    row=row,
                    parameters=parameters,
                    additional_parameters=kwargs,
                )
                yield (context, result) if yield_context else result
            return
```

Concurrent branch — change `process_with_semaphore_async` to return `tuple[ParallelFunctionContext, TOutput]` always (internal-only change, not observable outside this method), and unwrap conditionally at the yield site:

```python
        async def process_with_semaphore_async(
            *, name: str, row1: TInput, task_index: int, total_task_count: int
        ) -> tuple[ParallelFunctionContext, TOutput]:
            context = ParallelFunctionContext(
                name=name,
                log_level=log_level,
                task_index=task_index,
                total_task_count=total_task_count,
            )
            if self.semaphore is None:
                result = await process_row_fn(
                    context=context, row=row1, parameters=parameters, additional_parameters=kwargs
                )
            else:
                async with self.semaphore:
                    result = await process_row_fn(
                        context=context, row=row1, parameters=parameters, additional_parameters=kwargs
                    )
            return context, result

        total_task_count: int = len(rows)

        pending: set[Task[tuple[ParallelFunctionContext, TOutput]]] = {
            asyncio.create_task(
                process_with_semaphore_async(
                    name=self.name, row1=row, task_index=i, total_task_count=total_task_count
                ),
                name=f"task_{i}",
            )
            for i, row in enumerate(rows)
        }

        try:
            while pending:
                done: set[Task[tuple[ParallelFunctionContext, TOutput]]]
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    try:
                        context, result = await task
                        yield (context, result) if yield_context else result
                    except Exception:
                        raise
        finally:
            for task in pending:
                task.cancel()
```

Amend `resource_type_started_event.py` — add at the end:

```python
    link_index: int
    """-1 for the start resource (not processed via AsyncParallelProcessor, so
    it has no row index). For links, the 0-based index of this link within
    the current graph_depth pass's row list — combined with graph_depth,
    forms a stable key for pairing this event with its corresponding
    ResourceTypeCompletionEvent, since resource_types alone is not always
    unique (a link can declare multiple types, two links at the same depth
    can declare the same type, and a type can recur at a later depth)."""
```

Amend `resource_type_completion_event.py` — replace the existing wrong parenthetical and add the new field:

```python
    resource_types: list[str]
    """Distinct resource type(s) actually returned for the completed link, taken
    from each yielded FhirGetResponse.resource_type — not from the graph
    definition's declared target types, so this reflects what was actually
    fetched. When a link returns zero resources, this falls back to the
    link's declared target type(s) instead of an empty list, so a caller that
    received ResourceTypeStartedEvent for this link always receives a
    matching completion event — use resource_count == 0 to distinguish this
    fallback case from a real non-empty result."""

    # ... resource_count, graph_depth, urls fields unchanged ...

    link_index: int
    """Same semantics as ResourceTypeStartedEvent.link_index — pairs this
    event with the ResourceTypeStartedEvent that preceded it."""
```

Amend `graph_retrieval_completed_event.py`'s `urls` docstring:

```python
    urls: list[str]
    """Union of every actual URL queried across the whole graph traversal
    (start resource + every link, every depth), params included. May be
    empty if every queried resource was served from cache or was
    scope-denied (no real HTTP request made), not just on the start
    resource's zero-result path. This event fires exactly once per call —
    including when the traversal raises or the caller closes/abandons the
    generator early — except in the unavoidable Python limitation where a
    caller lets the generator become unreachable without an explicit
    break/aclose()."""
```

Rewrite `_process_simulate_graph_by_resource_type_async`'s body (from `if not isinstance(id_, list):` through the end) to: wrap the traversal in `try/finally` firing `on_graph_retrieval_completed` exactly once from `finally`; initialize the aggregation variables (`all_resource_types`, `total_resource_count`, `max_graph_depth`, `all_urls`) before anything that can raise; pass `yield_context=True` and unpack `context, link_responses` from the parallel processor; use `context.task_index` as `link_index`; filter empty-string URLs at capture; and make the per-row `on_resource_type_completed` firing unconditional (with declared-type fallback via `links[context.task_index].target`) per Design Decision 3 above. Apply exactly the design decisions listed above — they are final, not open questions.

Add the started-event's `link_index=-1` to its existing firing point (for the start resource), and add `link_index=context.task_index` to `process_link_async_parallel_function`'s `on_resource_type_started` firing (it already has `context` in scope as its first parameter — no new plumbing needed there).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest helix_fhir_client_sdk/graph/test/ helix_fhir_client_sdk/utilities/async_parallel_processor/v1/test/ -v` and `uv run mypy helix_fhir_client_sdk/`.

- [ ] **Step 5: Run the full regression suite**

Run: `uv run pytest helix_fhir_client_sdk/ -v` to confirm nothing outside the graph module regressed (the `AsyncParallelProcessor` change, though additive, touches a shared utility).

- [ ] **Step 6: Commit**

```bash
git add helix_fhir_client_sdk/utilities/async_parallel_processor/v1/async_parallel_processor.py helix_fhir_client_sdk/utilities/async_parallel_processor/v1/test/test_async_parallel_processor.py helix_fhir_client_sdk/graph/resource_type_started_event.py helix_fhir_client_sdk/graph/resource_type_completion_event.py helix_fhir_client_sdk/graph/graph_retrieval_completed_event.py helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py helix_fhir_client_sdk/graph/test/test_resource_type_started_event.py helix_fhir_client_sdk/graph/test/test_resource_type_completion_event.py helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "DCON-4509 add link_index correlation key, always-fire on_resource_type_completed, guarantee on_graph_retrieval_completed fires exactly once"
```

---

## Self-review notes (for whoever executes this plan)

- **Spec coverage:** Phase 2 §6's bullet "Either shape requires `simulate_graph_async()` to expose a per-resource-type completion hook" is satisfied by Tasks 1-2 (for `simulate_graph_by_resource_type_async`, the method actually used in production — not `simulate_graph_async`, which is a different, non-streaming method with no per-type boundary and is out of scope here since `helix.pipelines` doesn't use it for the default FHIR-retriever path).
- **What this plan deliberately does NOT do:** it does not touch `SubscriptionStatus`, Kafka, or any FHIR modeling — those are `helix.pipelines`-owned decisions requiring an FDR / AsyncAPI update per the spec's §10, and live entirely in the companion plan.
- **Placeholder scan:** resolved. An earlier draft of this plan left `fhir_client_with_mock_responses` and `SOME_TWO_LINK_GRAPH` as guessed placeholders. Both have been replaced with concrete code that mirrors the actual, confirmed convention in `helix_fhir_client_sdk/graph/test/test_simulate_graph_processor_mixin.py`: no pytest fixtures at all, just a `TestGraphProcessor(FhirClient)` subclass, `get_graph_processor()` helper, and `aioresponses()` HTTP-level mocking.
- **Convention fixes applied on review:** test paths corrected to `helix_fhir_client_sdk/graph/test/` (this repo has no `tests/graph/`); commit messages corrected to lead with the `DCON-4509` ticket key instead of conventional-commit prefixes (`feat:`/`test:`/`chore:`), matching every real commit in this repo's history; the old Task 4's manual `VERSION` bump was replaced (now Task 7) because `.github/workflows/python-publish.yml` derives `VERSION` from the GitHub release tag automatically — it's never hand-edited; and the `graph_depth` increment in Task 2 was moved to the end of the `while` loop body so first-level links actually fire at depth 0, matching Task 1's own docstring and test (the original placement would have fired depth 1 for first-level links, contradicting Task 1).
- **Scope extension after Tasks 1-3 shipped:** during execution, the goal grew from one callback (`on_resource_type_completed`) to a full four-callback lifecycle — `on_resource_type_started`, `on_graph_retrieval_started`, `on_graph_retrieval_completed` were added as Tasks 4-6 (renumbering the original Task 4 to Task 7), each event carrying the actual queried URL(s) so a callback shared across concurrent per-patient calls can tell which call an event belongs to. This required amending Task 1/2's already-committed `ResourceTypeCompletionEvent` (a new `urls` field) rather than rewriting history — see Task 4's design note for why "completed" events get real per-request URLs (read off `FhirGetResponse.url` before this file's pre-existing overwrite-with-base-URL line runs) while "started" events only get the connection's base URL (the specific query isn't constructed yet at that point).
- **Final whole-branch review after Task 7:** found the mechanical implementation (Tasks 1-7) sound but surfaced 5 Important, plan-level API-contract gaps this plan itself had never considered — not implementer bugs. Task 8 fixes all of them: a stable `link_index` correlation key, `on_resource_type_completed` firing unconditionally (declared-type fallback) so it always has a `started` counterpart, `on_graph_retrieval_completed` firing from a single `try/finally` so it's genuinely guaranteed once per call, empty-string URL filtering, three corrected docstrings, and the previously-missing `graph_depth > 0` test. Task 8 is explicitly the last fix wave — per this session's process, adjudicate any residual review findings after it rather than starting a third round.
