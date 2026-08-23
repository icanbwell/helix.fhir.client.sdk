# Error & Rejection Visibility for `simulate_graph_by_resource_type_async()`

**Status:** Implemented · **Ticket:** DCON-5229 (follow-on to the completion-hook feature; related to EA-2509) · **Repo:** `helix.fhir.client.sdk`

## Problem

`simulate_graph_by_resource_type_async()` (design: `docs/superpowers/specs/2026-08-22-resource-type-completion-hook-design.md`) added a four-callback event lifecycle so `helix.pipelines` can drive per-resource-type progress UI and Kafka publishing during a `$graph` traversal. That lifecycle tells a caller *when* a resource type finished, but not *how* — three outcomes are all currently indistinguishable from a caller's perspective:

- A resource type that returned zero results because there was genuinely nothing to fetch (e.g. no matching reference on the parent).
- A resource type the auth scope denied — the fetch never happened at all.
- A resource type the FHIR source explicitly returned 404 for.

And a fourth case is worse than indistinguishable — it's invisible until it's fatal: today, if a link's own fetch raises (network error, 5xx, timeout), `on_resource_type_completed` fires once with `resource_count=0` and then the exception propagates, aborting the entire `$graph` traversal — including every link that hasn't run yet, even ones with no relationship to the failure. A caller building a progress UI or a partial-data pipeline has no way to say "AllergyIntolerance failed, but keep going and get me what else is available."

## Goal

1. Give every `ResourceTypeCompletionEvent` a precise `outcome`, so a caller can render "no data," "not permitted," "not found," or "failed" as distinct states instead of one undifferentiated "0 resources."
2. Let a caller opt into resilience: a single resource type's fetch failure no longer has to take down the whole traversal.
3. Give the whole-graph bookend event (`GraphRetrievalCompletedEvent`) rollup counts so a caller doesn't have to tally outcomes itself just to answer "did anything go wrong, and how much."

## Non-Goals

- No change to `simulate_graph_async()` (the non-streaming sibling) — same scoping rationale as the original feature: it has no per-resource-type boundary and isn't `helix.pipelines`' retrieval path.
- No retry logic. A failed resource type is reported and skipped (or aborts, depending on mode) — this SDK does not re-attempt it.
- No new outcome for cache-hit responses. `url == ""` already conflates "served from cache" and "scope-denied" (documented in the original design as intentional), and this design does not change what's in `urls` — it only adds a way to tell scope-denial apart from a real zero-result using a different, more direct signal (see below), without touching the existing `urls` semantics.
- Does not change what happens when the **start resource** fetch fails — that stays fatal in every mode (see Key Decision 3).

## Key design decisions

**1. `outcome` is a closed, additive enum on `ResourceTypeCompletionEvent`: `"success" | "empty" | "not_found" | "scope_denied" | "error"`.** Precedence when a link's aggregated responses could imply more than one (a link can have multiple targets): `resource_count > 0` → `"success"`; else any constituent response has `status == 404` → `"not_found"`; else the link's declared target type(s) are scope-denied (see Decision 2) → `"scope_denied"`; else → `"empty"` (today's only zero-result case: a forward/reverse reference existed on the parent search path but no ID search actually matched, or the link had no references to follow at all). `"error"` is set only on the exception path (Decision 4) and is mutually exclusive with the others — an errored fetch never produced a response to classify. This is purely additive to the event's payload; the field is required (not optional) since every completion event has exactly one outcome, avoiding a `None`-means-what-exactly ambiguity.

One link can declare more than one target type, so its constituent responses can have mixed outcomes (e.g. one target returns resources while a second is scope-denied). The precedence order above is applied across *all* of the link's responses combined, not per-target — a single link fires exactly one `ResourceTypeCompletionEvent`, so it gets exactly one `outcome`. Concretely: if any target returned resources, the link's outcome is `"success"` even if a sibling target within the same link was denied or 404'd; that sibling's specific fate is not separately reported. This is an accepted, explicit simplification, not an oversight — the original design already reports mixed multi-target links as one combined event (see its `resource_types` field, which is a list precisely because of this), and this design does not change that granularity.

**2. `scope_denied` is detected by asking the scope parser directly, not by inspecting the response.** `url == ""` already means "either cache-hit or scope-denied" (existing, intentional conflation per the original design) — response shape alone cannot distinguish them. `GraphLinkParameters` already carries `scope_parser`, so the fix is to ask it directly: at the point a link's completion event is built, check `scope_parser.scope_allows(resource_type=t)` for the link's declared target type(s). If none of them are allowed, the outcome is `scope_denied` regardless of what the (nonexistent) response looked like. This mirrors exactly how `_get_resources_by_parameters_async` itself decides to skip the fetch — same predicate, asked again at the reporting site instead of inferred after the fact.

**3. The start resource's own fetch failure is always fatal, in every mode.** There are no links, no parent bundle, nothing to traverse without it — "continue anyway" would mean immediately reaching the already-existing zero-results early-return path, which is a different, pre-existing code path and not what "resilience" is asking for here. `on_resource_type_completed` still fires for the start resource with `outcome="error"` before the exception propagates (this part is unconditional — it doesn't depend on Decision 4's flag, since the start resource was never in scope for "continue on error" in the first place).

**4. Link-level fetch failures become non-fatal only behind a new opt-in parameter, `continue_on_resource_type_error: bool = False`.** Default `False` is a deliberate, hard requirement: the original feature's entire premise is "every one of these defaults to off; a caller that doesn't opt in sees zero behavior change." A caller today may already be relying on the exception propagating (e.g. wrapping the `async for` in `try/except FhirSenderException` to treat any failure as fatal for its own retry/alerting logic) — silently changing that default would be a breaking change disguised as an additive one. When `True`: a link's fetch failure fires `on_resource_type_completed` with `outcome="error"`, `error_type` (the exception's class name), and `error_message` (`str(exc)`), then the traversal moves on to the next link/parent-link-map entry instead of re-raising. When `False` (default): identical to today — fire the completion event, then re-raise, aborting the traversal.

**5. `asyncio.CancelledError` is never treated as a resource-type error, in either mode.** Cancellation means the caller (or a sibling task, per the recent `AsyncParallelProcessor` fix) is shutting this down — it is not information about *this resource type's* fetch, and swallowing it to "continue the traversal" would fight asyncio's own cancellation contract. `continue_on_resource_type_error` only changes handling of `Exception`; `CancelledError` always propagates immediately, in both modes, matching the just-shipped fix's behavior of always firing the matching completion event first.

**6. A failed link's nested `target.link` children are skipped entirely — no events fire for them.** Nested links only exist to traverse the parent bundle the failed fetch would have produced; there is no parent data to traverse from, so there is nothing to declare a `started`/`completed` pair for. This also means `max_graph_depth` on `GraphRetrievalCompletedEvent` may end up shallower than the graph definition declares, for a traversal that hit an error — expected, not a bug.

**7. `GraphRetrievalCompletedEvent` gets two new, separately-tracked rollups: `total_error_count` and `total_rejected_count`.** Kept apart deliberately: `total_error_count` counts real fetch failures (`outcome="error"`, including the start resource) — the number a caller would alert or retry on. `total_rejected_count` counts scope-denials (`outcome="scope_denied"`) — an expected authorization outcome, not a failure; folding it into the same counter would make error-rate alerting fire on routine, by-design scope restrictions. `not_found` and `empty` are not counted in either rollup — both are normal, successful-request outcomes that happen to carry zero resources, not failures of any kind.

## What changes in the public API

- **New, required field** on `ResourceTypeCompletionEvent`: `outcome: Literal["success", "empty", "not_found", "scope_denied", "error"]`.
- **New, optional fields** on `ResourceTypeCompletionEvent`, populated only when `outcome == "error"`: `error_type: str | None`, `error_message: str | None`. Both `None` for every other outcome.
- **New fields** on `GraphRetrievalCompletedEvent`: `total_error_count: int`, `total_rejected_count: int`.
- **New keyword-only parameter** on `simulate_graph_by_resource_type_async()`: `continue_on_resource_type_error: bool = False`. Default preserves today's behavior exactly.
- No changes to `ResourceTypeStartedEvent`, `GraphRetrievalStartedEvent`, or any yielded `FhirGetResponse` — this remains a pure side channel plus one opt-in control-flow change, exactly as constrained by the Non-Goals.

## Rollout

Additive change to the event payloads (new required field on an existing dataclass is a source-breaking change for any caller constructing `ResourceTypeCompletionEvent` directly — none should exist outside this SDK's own tests, since callers only ever *receive* these, never construct them). The new parameter defaults to off. Recommend shipping as the next **minor** version, same as the original feature, with a ticket created and linked before implementation (per this org's commit-message convention, every commit needs a JIRA key).
