# Per-Resource-Type Completion Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give callers of `simulate_graph_by_resource_type_async()` an explicit, concurrency-safe callback that fires each time one `GraphDefinition` link (i.e. one resource type, or occasionally a small set of them) has been *fully* retrieved, so consumers can report real progress ("now retrieving Condition...") without reverse-engineering completion from yield ordering.

**Architecture:** Add one new optional parameter, `on_resource_type_completed`, threaded from the public `simulate_graph_by_resource_type_async()` down to the private generator `_process_simulate_graph_by_resource_type_async()`. Fire it (a) once for the start resource right after it's yielded, and (b) once per outer-loop row, right after that row's full `link_responses` list has been drained into individual yields. Resource type(s) and count are derived from the *actual* `FhirGetResponse.resource_type` / `get_resource_count()` values already present on each yielded response — not from the `GraphDefinition` — so the event reflects what was actually fetched. No existing signature's *return type* changes; the new parameter defaults to `None` (no-op), so this is fully backward compatible.

**Tech Stack:** Python 3.12+, asyncio, this repo's existing `helix_fhir_client_sdk.graph.simulated_graph_processor_mixin` module.

**Spec:** Phase 2 of `docs/superpowers/specs/2026-08-22-data-connection-status-design.md` in `mcp-fhir-agent` (path at time of writing: `/Users/imranqureshi/git/mcp-fhir-agent/.claude/worktrees/IQ-EA-2509-view/docs/superpowers/specs/2026-08-22-data-connection-status-design.md`), §6. That doc assumed `simulate_graph_async()` had *no* per-resource-type hook at all. That's out of date for this method specifically: `simulate_graph_by_resource_type_async()` (added in commit `abdae63` "DCON-3865 Added fn to retrieve data in streaming way") already yields one `FhirGetResponse` per resource-type chunk, and `helix.pipelines` already consumes it by default for FHIR-based PROA connections (see the companion plan in `helix.pipelines`, Task 1, for the call-chain evidence). What's genuinely missing — and what this plan adds — is an *explicit* "this resource type is done" signal, because today a consumer can only infer completion by watching for `resource_type` to change between consecutive yields, which is only safe when `max_concurrent_tasks == 1` (the pipeline's own default, but not a documented contract of this method).

## Global Constraints

- Zero behavior change for existing callers: the new parameter is optional, defaults to `None`, and when `None` no new code path executes.
- No change to the yielded `FhirGetResponse` sequence, ordering, or count — this is purely an additional side channel.
- Must work correctly regardless of `max_concurrent_tasks` (i.e., don't bake in an assumption that rows complete in submission order) — this is the entire point of making the signal explicit instead of inferred.
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

## Task 4: Coordinate the release with `helix.pipelines`

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

## Self-review notes (for whoever executes this plan)

- **Spec coverage:** Phase 2 §6's bullet "Either shape requires `simulate_graph_async()` to expose a per-resource-type completion hook" is satisfied by Tasks 1-2 (for `simulate_graph_by_resource_type_async`, the method actually used in production — not `simulate_graph_async`, which is a different, non-streaming method with no per-type boundary and is out of scope here since `helix.pipelines` doesn't use it for the default FHIR-retriever path).
- **What this plan deliberately does NOT do:** it does not touch `SubscriptionStatus`, Kafka, or any FHIR modeling — those are `helix.pipelines`-owned decisions requiring an FDR / AsyncAPI update per the spec's §10, and live entirely in the companion plan.
- **Placeholder scan:** resolved. An earlier draft of this plan left `fhir_client_with_mock_responses` and `SOME_TWO_LINK_GRAPH` as guessed placeholders. Both have been replaced with concrete code that mirrors the actual, confirmed convention in `helix_fhir_client_sdk/graph/test/test_simulate_graph_processor_mixin.py`: no pytest fixtures at all, just a `TestGraphProcessor(FhirClient)` subclass, `get_graph_processor()` helper, and `aioresponses()` HTTP-level mocking.
- **Convention fixes applied on review:** test paths corrected to `helix_fhir_client_sdk/graph/test/` (this repo has no `tests/graph/`); commit messages corrected to lead with the `DCON-4509` ticket key instead of conventional-commit prefixes (`feat:`/`test:`/`chore:`), matching every real commit in this repo's history; Task 4's manual `VERSION` bump was replaced because `.github/workflows/python-publish.yml` derives `VERSION` from the GitHub release tag automatically — it's never hand-edited; and the `graph_depth` increment in Task 2 was moved to the end of the `while` loop body so first-level links actually fire at depth 0, matching Task 1's own docstring and test (the original placement would have fired depth 1 for first-level links, contradicting Task 1).
