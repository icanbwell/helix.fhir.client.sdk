# Extending the Completion-Hook Event Lifecycle to `simulate_graph_async()` and `simulate_graph_streaming_async()`

**Status:** Draft · **Ticket:** TBD (create before implementation, per commit-message convention) · **Repo:** `helix.fhir.client.sdk`

## Problem

`simulate_graph_by_resource_type_async()` has a full event lifecycle (`on_graph_retrieval_started`, `on_resource_type_started`, `on_resource_type_completed`, `on_graph_retrieval_completed`), outcome/error visibility (`ResourceTypeCompletionEvent.outcome`, `error_type`, `error_message`), and an opt-in `continue_on_resource_type_error` — see `docs/superpowers/specs/2026-08-22-resource-type-completion-hook-design.md` and `docs/superpowers/specs/2026-08-23-resource-type-error-visibility-design.md`. Both design docs explicitly scoped `simulate_graph_async()` (and, by the same reasoning, `simulate_graph_streaming_async()`) out, on the grounds that neither has "a per-resource-type boundary."

Callers of those two methods — which share a common core, `process_simulate_graph_async()` — have no progress visibility at all today: no signal for when the traversal starts, when an individual resource type starts/finishes, or when it's done, and no way to distinguish "no data" from "not permitted" from "failed."

## Goal

Give `simulate_graph_async()` and `simulate_graph_streaming_async()` the exact same event/outcome/resilience API `simulate_graph_by_resource_type_async()` already has, as a pure side channel — no change to what either method returns/yields, its order, or its count, for a caller that passes none of the new parameters.

## Non-Goals

- No change to the *shape* of what's returned. `simulate_graph_async()` still returns one merged `FhirGetResponse`; `simulate_graph_streaming_async()` still yields the same sequence it yields today (typically once, or once early on a zero-result start resource). This work does not make either method chunk per resource type — that granularity remains exclusive to `simulate_graph_by_resource_type_async()`.
- No change to `_process_simulate_graph_by_resource_type_async()` or its tests — that method and its event wiring are untouched by this work.
- No retry logic, no new outcome values, no schema changes to any of the four event dataclasses — all four are reused exactly as they exist today.

## Key design decisions

**1. Extend the shared core, `process_simulate_graph_async()`, rather than duplicating its ~190-line traversal loop into a new private method.** Both public methods delegate to it today; adding the same optional (`None`/`""`/`False`-defaulted) event parameters directly to it, and having both public wrappers forward them, keeps one traversal implementation instead of two to keep in sync. A caller of either public method that passes none of the new parameters exercises the exact same code paths as today (every new branch is `if on_xxx:` / `if continue_on_resource_type_error:`, defaulting to skip).

**2. Both `simulate_graph_async()` and `simulate_graph_streaming_async()` get the full parameter set** — `on_resource_type_completed`, `on_resource_type_started`, `on_graph_retrieval_started`, `on_graph_retrieval_completed`, `client_person_id`, `connection_name`, `continue_on_resource_type_error` — identical names, types, and defaults to `simulate_graph_by_resource_type_async()`. This was a deliberate scope decision (superseding the original design docs' Non-Goal for `simulate_graph_async()`), made explicitly for this change rather than inferred.

**3. Per-link outcome classification and event firing reuse `_fire_on_resource_type_completed_for_link()` as-is.** It's already a standalone instance method (not a nested closure tied to `_process_simulate_graph_by_resource_type_async()`'s local scope), so `process_simulate_graph_async()`'s consumer loop can call it directly. A new nested closure inside `process_simulate_graph_async()` (mirroring `_record_link_batch_outcome`) captures that call plus the `nonlocal` rollup updates (`all_resource_types`, `total_resource_count`, `max_graph_depth`, `all_urls`, `total_error_count`, `total_rejected_count`) local to `process_simulate_graph_async()`'s own scope. No changes to `_fire_on_resource_type_completed_for_link()` itself.

**4. The start resource gets the same wrapping `process_simulate_graph_by_resource_type_async()` uses**, fired inside `process_simulate_graph_async()`:
   - `on_graph_retrieval_started` and `on_resource_type_started` (types=`[start]`, `graph_depth=0`, `link_index=-1`) before the fetch.
   - `(Exception, asyncio.CancelledError, GeneratorExit)` around the fetch itself fires the matching `on_resource_type_completed` (outcome `"error"` for a real `Exception`, `"empty"` for cancellation/close) before re-raising — never suppressing the exception.
   - On a successful fetch, `on_resource_type_completed` fires with `outcome` classified the same way (`"not_found"` on `status == 404`, `"error"` on any other unsuccessful status with a synthesized `HttpStatus<code>` `error_type`, `"success"` otherwise) — **without changing the existing `parent_response_resource_count == 0` early-return branching**, which stays exactly as it is today. The event's outcome is computed from the response's actual content; the decision to early-return is not.
   - `total_error_count` is incremented on the early-return path only for a genuinely-unsuccessful non-404 response, matching the same accounting rule already used in `_process_simulate_graph_by_resource_type_async()`.

**5. `graph_depth` tracking is added to `process_simulate_graph_async()`'s link-traversal `while` loop** (`graph_depth = 0` before it, `+= 1` at the end of each pass) — it doesn't exist there today because nothing needed it before. `GraphLinkParameters` already carries a `graph_depth` field; this just populates it here the way `_process_simulate_graph_by_resource_type_async()` already does.

**6. `process_rows_in_parallel(...)` is called with `yield_context=True`** (currently omitted, defaulting to `False`) so the consumer loop can recover `context.task_index` for `link_index` and for `_fire_on_resource_type_completed_for_link()`'s lookup into `links[context.task_index].target`. This is purely internal — `process_simulate_graph_async()`'s own callers never see `ParallelFunctionContext`.

**7. `continue_on_resource_type_error` requires no new exception-handling logic** — `process_link_async_parallel_function()` (already shared by both traversal implementations) already returns `_LinkFetchResult(responses=[], error=exc)` instead of raising when the flag is set. `process_simulate_graph_async()`'s loop already does `child_responses.extend(link_fetch_result.responses)`; adding the accounting closure's check of `link_fetch_result.error` (mirroring `_record_link_batch_outcome`) is sufficient to fire the correct `outcome="error"` completion event and continue to the next link, exactly as the by-resource-type method already does.

**8. `on_graph_retrieval_completed` fires from one `try/finally` wrapping `process_simulate_graph_async()`'s traversal**, identical in placement and reasoning to the existing method — fires exactly once, including on exception or the caller closing/abandoning the generator early.

## What changes in the public API

- New keyword-only parameters, identical names/types/defaults to `simulate_graph_by_resource_type_async()`, added to **both** `simulate_graph_async()` and `simulate_graph_streaming_async()`: `on_resource_type_completed`, `on_resource_type_started`, `on_graph_retrieval_started`, `on_graph_retrieval_completed`, `client_person_id: str = ""`, `connection_name: str = ""`, `continue_on_resource_type_error: bool = False`.
- `process_simulate_graph_async()` (internal, but shared) gains the same parameter set.
- No changes to any event dataclass (`ResourceTypeStartedEvent`, `ResourceTypeCompletionEvent`, `GraphRetrievalStartedEvent`, `GraphRetrievalCompletedEvent`) — all reused as-is.
- No changes to `simulate_graph_by_resource_type_async()` or `_process_simulate_graph_by_resource_type_async()`.

## Testing

New test module(s) mirroring `helix_fhir_client_sdk/graph/test/test_simulate_graph_by_resource_type_async_completion_hook.py`'s coverage, parameterized or duplicated across both `simulate_graph_async()` and `simulate_graph_streaming_async()`:

- Full event lifecycle fires in order, at `max_concurrent_tasks=1` and `>1`.
- `on_resource_type_completed` fires exactly once per link, including under concurrency.
- Every `started` gets a matching `completed`: zero-result links, zero-result start resource, links with no declared `target`, nested links at depth ≥ 1.
- `on_graph_retrieval_completed` fires exactly once: on normal completion, on exception, on explicit `aclose()`/early consumer abandonment (including via the public method).
- Outcome classification: `success`, `empty`, `not_found`, `scope_denied`, `error` (both raised-exception and non-404 HTTP-error-response forms), for both links and the start resource.
- `total_error_count`/`total_rejected_count` rollups on `GraphRetrievalCompletedEvent`.
- `continue_on_resource_type_error`: `False` (default) still aborts on a link failure; `True` continues past it, skips a failed link's nested children, and never swallows `asyncio.CancelledError`; start resource failure is always fatal regardless of the flag.
- A callback's own exception is not miscounted as a fetch failure.
- Backward compatibility: calling either method with none of the new parameters produces output identical to today (regression guard against the wiring changes above).
- `mypy --strict` and `ruff check`/`ruff format --check` clean across all touched files, per repo convention.

## Rollout

Additive, backward-compatible — semver **minor**. Every new parameter defaults to `None`/`""`/`False`; no existing caller of `simulate_graph_async()` or `simulate_graph_streaming_async()` is affected.
