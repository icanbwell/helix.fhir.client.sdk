# Per-Resource-Type Progress Events for `simulate_graph_by_resource_type_async()`

**Status:** Implemented, in final review · **Ticket:** DCON-4509 (SDK-side half of EA-2509 Phase 2) · **Repo:** `helix.fhir.client.sdk`

## Problem

`simulate_graph_by_resource_type_async()` streams a FHIR `$graph` traversal (Patient → Condition → Observation → ...) as a sequence of `FhirGetResponse` chunks, one per resource type. Callers building a progress UI ("connecting... now retrieving Condition... done") had no explicit signal for *when* one resource type's retrieval starts or finishes, or when the whole traversal starts or finishes. The only option was inferring completion from watching `resource_type` change between consecutive yields — which is silently wrong once `max_concurrent_tasks > 1`, since chunks can then arrive out of submission order.

This SDK is used by `helix.pipelines` to drive real-time PROA (Patient Reported Outcome... — data-connection) progress tracking. Phase 1 of EA-2509 already ships connection-level status. Phase 2 wants resource-type-level granularity, which requires this SDK to say so explicitly rather than making the caller guess.

## Goal

Give callers an explicit, concurrency-safe event lifecycle instead of an implicit ordering assumption. Four optional callbacks, fully backward compatible (every one defaults to `None`; a caller that doesn't pass any of them sees zero new code execute and zero change to the existing yielded response stream):

| Callback | Fires | Payload |
|---|---|---|
| `on_graph_retrieval_started` | once, before the start resource (e.g. Patient) is fetched | `GraphRetrievalStartedEvent` |
| `on_resource_type_started` | once per resource type/link, right before that retrieval begins | `ResourceTypeStartedEvent` |
| `on_resource_type_completed` | once per resource type/link, right after it's fully retrieved (or determined empty) | `ResourceTypeCompletionEvent` |
| `on_graph_retrieval_completed` | exactly once, after the whole traversal ends — including on error or early abandonment | `GraphRetrievalCompletedEvent` |

## Non-Goals

- No changes to what's yielded, its order, or its count — this is a pure side channel.
- No FHIR modeling, `SubscriptionStatus`, or Kafka changes — those are `helix.pipelines`-owned and tracked in the companion plan there.
- No support for `simulate_graph_async()` (the non-streaming sibling method) — it has no per-resource-type boundary and isn't the method `helix.pipelines` uses for the default retriever path.

## Key design decisions

**Declared types on the way in, actual types on the way out.** `on_resource_type_started` reports the resource type(s) *declared* on the `GraphDefinition` link's `target` array, because nothing has been fetched yet. `on_resource_type_completed` reports the type(s) *actually returned*, read off each `FhirGetResponse.resource_type`. These can differ (a link can declare more types than it ends up returning) — that's intentional, not a bug.

**Every `started` event gets a matching `completed` event.** A resource type that returns zero results still fires `on_resource_type_completed` (with `resource_count=0`, falling back to the declared type since nothing came back to report). Without this, a progress UI has no way to know a zero-result retrieval finished — it would show "retrieving X..." forever, which is common in practice (a `GraphDefinition` link like `Patient.generalPractitioner` fires nothing when the patient has no such reference). The same guarantee holds if the fetch itself raises: `completed` still fires (with `resource_count=0`) before the exception propagates, so a caller isn't left waiting on a signal that will never come. This also required making `started` unconditional — it used to skip links with no declared `target`, which meant such a link's (unconditional) `completed` had no matching `started` at all.

**Started and completed events are correlated by `(graph_depth, link_index)`, not by resource type.** Resource-type strings aren't a reliable pairing key: a single link can declare multiple types with partial results, two different links at the same depth can declare the same type, and — because a `GraphDefinition` can reference the same resource type at more than one nesting level — a type can legitimately recur later in the traversal. `link_index` is `-1` for the start resource and the link's position within its own concurrent batch otherwise, giving callers a stable way to pair events regardless of concurrency.

**`urls` for server-side correlation; `client_person_id`/`connection_name` for caller-side correlation.** Each per-resource-type event carries the actual URL(s) queried (with parameters — e.g. `.../AllergyIntolerance?patient=123`), which is enough to distinguish concurrent calls by what was actually fetched, without this SDK needing to know anything about "patients" or "connections." (URLs can be empty when a resource was served entirely from cache or was scope-denied — no real HTTP request happened — and are filtered out rather than reported as a misleading `""`.) That's sufficient for the SDK's own needs, but `helix.pipelines` — the actual consumer — needs to correlate events back to its own domain concepts (which person, which connection) to build Kafka payloads, and doing that by re-parsing query parameters out of a URL string is exactly the kind of fragile, indirect lookup a purpose-built field avoids. So `client_person_id` and `connection_name` were added as a second, complementary pair: caller-supplied, opaque strings this SDK never inspects, just echoes back on every event — same mechanism as `urls`, just carrying the caller's own identifiers instead of ones this SDK derived itself.

**`on_graph_retrieval_completed` fires from exactly one place: a `finally` block wrapping the whole traversal.** This guarantees it fires once per call — on normal completion, on the zero-result start-resource path, on an exception from anywhere in the traversal, and when a caller stops consuming the generator early (Python's `async for` calls `aclose()` on break, which runs `finally`). The one case this can't cover is a caller that lets the generator become unreachable without an explicit `break`/`close()` — that's a general limitation of Python async generators, not specific to this feature.

**Concurrency changes what you can assume about ordering, not correctness.** `on_resource_type_started` fires from inside the per-link task itself (since links can run concurrently under `max_concurrent_tasks > 1`), while `on_resource_type_completed` and both whole-graph bookends fire from the single-threaded consumer loop. The guarantee that holds regardless of concurrency: each resource type's own `started` precedes its own `completed`, and the two bookend events each fire exactly once, before/after everything else. What does *not* hold under concurrency: two different resource types' `started` events firing in a specific relative order — don't build UI logic that depends on that.

## What changed in the public API

- New: `ResourceTypeStartedEvent`, `GraphRetrievalStartedEvent`, `GraphRetrievalCompletedEvent`.
- Amended (additive): `ResourceTypeCompletionEvent` gained `urls: list[str]` and `link_index: int`. `ResourceTypeStartedEvent` also carries `link_index`. All four event types carry `client_person_id: str` and `connection_name: str`.
- New keyword-only parameters on `simulate_graph_by_resource_type_async()`: `on_resource_type_started`, `on_graph_retrieval_started`, `on_graph_retrieval_completed` (alongside the already-shipped `on_resource_type_completed`), plus `client_person_id`/`connection_name` (opaque pass-through strings, echoed onto every fired event). All default to `None`/`""` — zero behavior change for existing callers.

## Rollout

Additive, backward-compatible change — semver **minor**, not patch. `helix.pipelines`' companion work should not wire up the new callbacks until this version is actually published (`VERSION` is set from the GitHub release tag at publish time, not hand-edited).
