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
- Test: `tests/graph/test_resource_type_completion_event.py` (check whether tests live under `tests/` or `helix_fhir_client_sdk/graph/test/` — this module's sibling files use a `test/` subpackage next to the code per existing convention; search for `test_graph_definition` first to confirm the pattern before creating the file)

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

Run: `pytest tests/graph/test_resource_type_completion_event.py -v` (adjust path once the convention from Task 1's file search is confirmed)
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

Run: `pytest tests/graph/test_resource_type_completion_event.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add helix_fhir_client_sdk/graph/resource_type_completion_event.py tests/graph/test_resource_type_completion_event.py
git commit -m "feat: add ResourceTypeCompletionEvent for per-resource-type progress signaling"
```

---

## Task 2: Thread `on_resource_type_completed` through `simulate_graph_by_resource_type_async`

**Files:**
- Modify: `helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py:1292-1499` (`simulate_graph_by_resource_type_async` and `_process_simulate_graph_by_resource_type_async`)
- Test: same test module as the existing tests for this method — run `grep -rln "simulate_graph_by_resource_type_async" tests/` first to find it; if none exist yet, create `tests/graph/test_simulate_graph_by_resource_type_async_completion_hook.py` next to wherever the existing streaming tests for this mixin live.

**Interfaces:**
- Consumes: `ResourceTypeCompletionEvent` from Task 1.
- Produces: new keyword-only parameter `on_resource_type_completed: Callable[[ResourceTypeCompletionEvent], Awaitable[None]] | None = None` on both `simulate_graph_by_resource_type_async` and `_process_simulate_graph_by_resource_type_async` — this exact parameter name and type is what `helix.pipelines` wires up (see the companion plan, Task 3).

- [ ] **Step 1: Write the failing test**

```python
import pytest

from helix_fhir_client_sdk.graph.resource_type_completion_event import (
    ResourceTypeCompletionEvent,
)

# Reuse whatever fixture/mock FhirClient this repo's existing
# simulate_graph_by_resource_type_async tests use to avoid a real network call —
# check test_simulate_graph_async.py or similar for the existing mock pattern
# and mirror it here rather than inventing a new one.


@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_once_per_link(
    fhir_client_with_mock_responses,  # replace with the actual fixture name found above
) -> None:
    events: list[ResourceTypeCompletionEvent] = []

    async def capture(event: ResourceTypeCompletionEvent) -> None:
        events.append(event)

    result = await fhir_client_with_mock_responses.simulate_graph_by_resource_type_async(
        id_="123",
        graph_json=SOME_TWO_LINK_GRAPH,  # a GraphDefinition with e.g. AllergyIntolerance + CarePlan links
        contained=False,
        max_concurrent_tasks=1,
        on_resource_type_completed=capture,
    )
    _ = [r async for r in result] if hasattr(result, "__aiter__") else None

    # one event for the start resource (Patient) + one per link
    assert len(events) == 3
    assert events[0].resource_types == ["Patient"]
    assert {"AllergyIntolerance", "CarePlan"} <= {
        t for e in events[1:] for t in e.resource_types
    }


@pytest.mark.asyncio
async def test_on_resource_type_completed_defaults_to_none_is_noop(
    fhir_client_with_mock_responses,
) -> None:
    # No callback passed — must behave exactly as before (regression guard for
    # the "zero behavior change for existing callers" constraint).
    responses = [
        r
        async for r in fhir_client_with_mock_responses.simulate_graph_by_resource_type_async(
            id_="123",
            graph_json=SOME_TWO_LINK_GRAPH,
            contained=False,
            max_concurrent_tasks=1,
        )
    ]
    assert len(responses) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/graph/test_simulate_graph_by_resource_type_async_completion_hook.py -v`
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
                graph_depth += 1

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
```

Note the event fires *after* the `for link_response in link_responses: yield link_response` loop for that row — the caller has already received every resource for this link by the time the event arrives, satisfying "fully retrieved" (not "about to start").

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/graph/test_simulate_graph_by_resource_type_async_completion_hook.py -v`
Expected: PASS

- [ ] **Step 5: Run the full existing test suite for this module to confirm no regression**

Run: `pytest tests/graph/ -v -k "simulate_graph"`
Expected: All pre-existing tests for `simulate_graph_async`, `simulate_graph_streaming_async`, and `simulate_graph_by_resource_type_async` still PASS unchanged (they don't pass `on_resource_type_completed`, exercising the default-`None` no-op path).

- [ ] **Step 6: Commit**

```bash
git add helix_fhir_client_sdk/graph/simulated_graph_processor_mixin.py tests/graph/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "feat: add on_resource_type_completed callback to simulate_graph_by_resource_type_async"
```

---

## Task 3: Verify behavior under `max_concurrent_tasks > 1` (documented limitation, not a fix)

**Files:**
- Test: same file as Task 2.

This task exists because the whole reason this hook is more valuable than the status quo is that it doesn't silently break if a future caller sets `max_concurrent_tasks > 1`. Verify — don't try to "fix" interleaving here, since `AsyncParallelProcessor.process_rows_in_parallel` already yields one row's *complete* result per row (see its implementation, `helix_fhir_client_sdk/utilities/async_parallel_processor/v1/async_parallel_processor.py`) even when running concurrently; each `link_responses` list is still a fully-drained result for its own row regardless of concurrency, so the event Task 2 added is correct as-is. This step is a regression test proving that claim, not new code.

- [ ] **Step 1: Write the test**

```python
@pytest.mark.asyncio
async def test_on_resource_type_completed_fires_correctly_at_concurrency_2(
    fhir_client_with_mock_responses,
) -> None:
    events: list[ResourceTypeCompletionEvent] = []

    async def capture(event: ResourceTypeCompletionEvent) -> None:
        events.append(event)

    async for _ in fhir_client_with_mock_responses.simulate_graph_by_resource_type_async(
        id_="123",
        graph_json=SOME_TWO_LINK_GRAPH,
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

Run: `pytest tests/graph/test_simulate_graph_by_resource_type_async_completion_hook.py -v -k concurrency`
Expected: PASS. If it fails, that's a real bug in `AsyncParallelProcessor` ordering assumptions — stop and re-examine `process_rows_in_parallel`'s semaphore-based branch (the `max_concurrent_tasks != 1` path) before proceeding; do not paper over it by forcing `max_concurrent_tasks=1` in the event-firing code.

- [ ] **Step 3: Commit**

```bash
git add tests/graph/test_simulate_graph_by_resource_type_async_completion_hook.py
git commit -m "test: verify on_resource_type_completed stays correct under concurrent link processing"
```

---

## Task 4: Version bump and changelog

**Files:**
- Modify: `VERSION` (referenced by `pyproject.toml:35` as `version = { file = "VERSION" }`)
- Modify: `CHANGELOG.md` if one exists (check repo root; if not, skip)

- [ ] **Step 1: Bump the version**

Check `VERSION`'s current value and bump the minor version (this is an additive, backward-compatible feature — semver minor, not patch, not major).

- [ ] **Step 2: Commit**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: bump version for on_resource_type_completed feature"
```

- [ ] **Step 3: Coordinate the release with `helix.pipelines`**

The companion plan in `helix.pipelines` (`docs/superpowers/plans/2026-08-22-proa-per-resource-type-progress.md`, Task 1) pins this exact version once published. Do not merge that plan's Task 1 until this SDK version is actually released (published to whatever package index `helix.pipelines`' `Pipfile` resolves `helix-fhir-client-sdk` from — check `Pipfile` there for the source).

---

## Self-review notes (for whoever executes this plan)

- **Spec coverage:** Phase 2 §6's bullet "Either shape requires `simulate_graph_async()` to expose a per-resource-type completion hook" is satisfied by Tasks 1-2 (for `simulate_graph_by_resource_type_async`, the method actually used in production — not `simulate_graph_async`, which is a different, non-streaming method with no per-type boundary and is out of scope here since `helix.pipelines` doesn't use it for the default FHIR-retriever path).
- **What this plan deliberately does NOT do:** it does not touch `SubscriptionStatus`, Kafka, or any FHIR modeling — those are `helix.pipelines`-owned decisions requiring an FDR / AsyncAPI update per the spec's §10, and live entirely in the companion plan.
- **Placeholder scan:** `fhir_client_with_mock_responses` and `SOME_TWO_LINK_GRAPH` are named placeholders for fixtures the executing engineer must locate (via the `grep` instructions in each task) or construct from this repo's existing test conventions — flagged explicitly rather than guessed, since the exact fixture names weren't visible from outside this repo's test suite at plan-writing time.
