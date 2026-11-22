# Implementation plan: orjson for the SDK's own JSON handling (BAI-1960)

Jira: BAI-1960. Implements `adrs/0001-faster-json-with-orjson.md` (PR #297). This document is the plan only; no code changes are in this PR. The implementation is on branch `IQ-BAI-1960-orjson-impl`; see Status. The ADR is the authority for every decision below; where this plan and the ADR disagree, the ADR wins and this plan is fixed. Line numbers come from the ADR (`f6e8e34`) and must be rechecked before editing.

## Constraints that apply

- **Tenancy:** none. No persistence or query changes.
- **PHI:** fixtures, benchmarks and tests use synthetic data only. No payload content in logs, span attributes or error text.
- **Public contract:** new `FhirClient.byte_identical_json()`; default response and request text changes. Released as a major version.
- **Event schemas:** none.
- **New dependency:** `orjson>=3.11.9` becomes a direct dependency. It is already locked through `compressedfhir`; the ADR records the governance decision.

## Preconditions (do not start the PR until all hold)

1. `fhir-server#2775` (DCON-6862) is merged and deployed.
2. PR #298 (`compressedfhir` 5.0.0 upgrade) is merged and released as its own major. The implementation branch starts from `main` after that merge, so `.json(byte_identical=...)` exists and `compressedfhir>=5.0.0` is locked.
3. The expected `raw_hash` values come from a checkout of `main` before #298 (`compressedfhir` 3.0.5), not from the post-upgrade tree. Capture them from that checkout and commit them as constants. See Phase 0.
4. ADR status is moved from proposed to accepted, and the two version numbers for the majors are decided.

## Delivery shape

One PR, all phases, one release (ADR Rollout): `main` must not carry a breaking phase that a weekly release would publish. Commit per phase so review can follow the order. Each phase leaves `uv run pytest helix_fhir_client_sdk/` and `uv run mypy helix_fhir_client_sdk/` green. Test-first within each phase: write the failing test, then the change.

Out of scope, separate PRs: `split("\n")` NDJSON fix (BAI-1965, #300) and payloads in error strings and logs (BAI-1964, #299). Rebase on them if they merge first; they touch `json_helpers.py` and the same test files.

## Phase 0: baseline and oracle (no behavior change)

1. Add `helix_fhir_client_sdk/utilities/test/legacy_json_oracle.py`: a verbatim copy of the current stdlib `dumps` logic (including `FhirJSONEncoder` use and default separators), used only by tests as the byte-for-byte oracle (ADR Tests 1).
2. Hash continuity fixture: a fixed synthetic resource, and one containing NaN, hashed with the current expression `sha256(json.dumps(json.loads(resource.json()), sort_keys=True))`. Record the expected hex digests from pre-#298 `main` as constants in a new test (ADR Tests 6). The test asserts equality with the constants, not only between modes.
3. Extend `tests/async/test_benchmark_merge.py` with before-numbers on Python 3.12: `dumps` and `loads` at 100, 1,000 and 10,000 entries, NDJSON per-line `loads`, and the maximum event-loop stall per call (run beside a ticking coroutine). Re-run the GIL thread-ratio check on 3.12 with repeated runs. Save the numbers in the PR description (ADR Tests 8).

## Phase 1: `fast_json` module and dependency

Files: `helix_fhir_client_sdk/utilities/fast_json.py`, `helix_fhir_client_sdk/utilities/test/test_fast_json.py`, `pyproject.toml`, `uv.lock`.

1. Declare `orjson>=3.11.9` in `pyproject.toml`; `uv lock` (the `exclude-newer = "2 days"` setting applies). Check whether `types-orjson` (`pyproject.toml:63`) is still needed, since orjson ships stubs; drop it only if mypy is clean without it.
2. `JsonDecodeError(json.JSONDecodeError)`, SDK-owned.
3. `dumps_str(obj: object, *, byte_identical: bool = False) -> str`:
   - `byte_identical=True`: stdlib path, identical to the oracle.
   - default: `orjson.dumps(obj, default=<FhirJSONEncoder-equivalent>, option=OPT_PASSTHROUGH_DATETIME | OPT_PASSTHROUGH_DATACLASS)`, decoded to `str`. The `default` hook covers `Decimal`, `bytes`, `Path`, `datetime`, dataclasses and objects with `to_dict` or `__dict__`. Decide `OPT_PASSTHROUGH_SUBCLASS` against the fixtures.
   - Catch `TypeError` from orjson and fall back to stdlib (big ints, int keys, `set`, lone surrogates); log the fallback at debug with no payload content.
4. `loads(text: str | bytes, *, byte_identical: bool = False) -> Any`: stdlib when `byte_identical`, otherwise `orjson.loads`, catching `orjson.JSONDecodeError` and raising `JsonDecodeError` with `raise ... from e`. Unguarded (ADR decision).
5. Telemetry: module-level `TRACER` as in `fhir_merge_mixin.py:38`. Set span attributes `json.operation`, `json.bytes`, `json.duration_ms`, `json.fallback`, `json.error` on the active span only; no new metrics instruments, no tenant or payload content. Verify there is no per-call span creation cost on the hot path (set attributes on the current span, do not start a span per call).
6. Tests (parameterized over both modes): ADR Tests 1, 2, 3 (module level), 3b, 3c. Include the parse-difference table: 30-digit integer, `NaN`, `Infinity`, `1e400`, depth 1100, lone surrogate, BOM.

Contract: return types stay `str`. Docstrings carry the behavior table (they feed `docs/autoapi`).

## Phase 2: the client flag and plumbing

Files: `fhir_client.py`, `responses/fhir_client_protocol.py`, `responses/fhir_response_processor.py`, the response classes, `utilities/retryable_aiohttp_client.py`, `utilities/retryable_aiohttp_response.py`.

1. `FhirClient.byte_identical_json(use: bool = True) -> FhirClient`, field `self._byte_identical_json: bool = False` beside `_content_type`, following the fluent setters at `use_data_streaming`, `content_type`, `compress`. Docstring states the contract and the behavior table.
2. Add the field to the clone code (`fhir_client.py:974-1038`). Test: a cloned client keeps the flag (ADR Tests 5).
3. Add the field to `FhirClientProtocol` (pattern at `responses/fhir_client_protocol.py:88`).
4. Thread it, the way `use_data_streaming` and `storage_mode` are carried:
   - `FhirResponseProcessor.handle_response` parameter.
   - Keyword-only `byte_identical_json: bool = False` on every response constructor, and copied in every `from_response` (base and subclasses) and every append path that builds a response.
   - `RetryableAioHttpClient` constructor argument, passed to each `RetryableAioHttpResponse` (8 construction sites); `RetryableAioHttpResponse.json()` uses it. Update `validators/async_fhir_validator.py` call site if it constructs the client.
5. Mechanical safety net: a test that enumerates response classes and fails if a constructor or `from_response` drops the flag (so a later new response type cannot silently revert to compact text).

## Phase 3: parse sites

Replace `json.loads` with `fast_json.loads(..., byte_identical=...)` at each site in the ADR table (response parse, error responses, `request_queue_mixin.py`, `fhir_delete_mixin.py`, merge response entries).

- `parse_json_or_ndjson` takes a keyword-only `byte_identical`; update callers `fhir_merge_mixin.py:227`, `fhir_merge_resources_mixin.py:172`, `fhir_merge_resource_response_entry.py:115`.
- `from_json` is an `@override` classmethod: add the argument to the base class and every override in the same commit (watch for Liskov: same signature everywhere).
- `fhir_merge_response_entry_issue.py:55`: keyword-only argument.
- Where `str(e)` is surfaced (`fhir_merge_mixin.py:234`, `fhir_patch_mixin.py:123`), confirm the message contains no payload content with the new error type.
- Test (ADR Tests 3): each parse site exercised with a 30-digit integer in both modes.

## Phase 4: streaming NDJSON parser

File: `utilities/ndjson_chunk_streaming_parser.py` (constructor takes the flag; split on `"\n"` at `:25`).

1. Failing test first (ADR Tests 3a): a stream with a NaN line, a lone-surrogate line and a deep-nesting line in the middle must raise or report, never drop; a genuinely partial final line is held for the next chunk.
2. Fix: only the last segment after the final `"\n"` is held; a decode failure on any earlier segment raises `JsonDecodeError` (or is reported to the caller, whichever matches the existing consumer contract; read the consumers before choosing).
3. Then switch the per-line parse to `fast_json.loads`.

## Phase 5: write sites

Replace `json.dumps` at the build-body and build-response-text sites in the ADR table with `fast_json.dumps_str(..., byte_identical=...)`: `fhir_merge_mixin.py`, `fhir_patch_mixin.py`, `fhir_response_processor.py`, `fhir_get_list_response.py`, `fhir_get_list_by_resource_type_response.py`, `fhir_get_error_response.py`.

- The three `cls=FhirJSONEncoder` sites move to the `default` hook; delete nothing from `FhirJSONEncoder` unless #298 proved it removable.
- Forward the flag as `.json(byte_identical=...)` to every `compressedfhir` text call listed in the ADR: `fhir_merge_resources_mixin.py`, `fhir_update_mixin.py`, `fhir_get_single_response.py`, `fhir_get_list_response.py`, `fhir_get_bundle_response.py`.
- Error and diagnostic text sites stay as they are unless they sit on the response path; do not widen scope.
- Tests (ADR Tests 5): assert `get_response_text()` and the sent request body in both modes; opted-in caller gets the old text from `get_response_text()` (this is the case review thread 1 on this PR raised).

## Phase 6: hash sites stay on stdlib

1. Add `stable_resource_hash_input(resource) -> str` in one place; it calls `resource.json(byte_identical=True)` with the flag **fixed**, then `json.dumps(json.loads(...), sort_keys=True)`.
2. Use it at `simulated_graph_processor_mixin.py:1521,1812` and `fhir_get_bundle_response.py:364`. Do not forward the client flag here.
3. The Phase 0 continuity test must pass unchanged, in both modes, including the NaN fixture.

## Phase 7: docs, cleanup, verification

1. README: a short upgrade section naming the breaking changes (default text, NaN as `null`, big-integer parse, raw UTF-8, fhir-server prerequisite) and linking to the API reference; no second copy of the table.
2. Rewrite exact-text test assertions to compare parsed JSON (pattern in `test_merge_streaming_request_body.py`).
3. Fill the ADR consumer-impact table (repo, outputs consumed, exact-text dependency, action) for the nine repos named there, before the release is cut. Update ADR open items and status.
4. Run on Python 3.12: full suite, benchmark (after-numbers next to Phase 0), cProfile of a representative graph traversal on the Provider New workload (ADR Tests 8) to settle the end-to-end claim. Do not advertise an end-to-end speedup unless this shows one.
5. Contract test against fhir-server `$merge` with a non-ASCII resource split across chunks (ADR Tests 9), once `fhir-server#2775` is deployed. Also settle the open item on `null` for NaN in a `$merge` body.
6. Consumer-facing release notes: breaking changes, `byte_identical_json()`, the fhir-server prerequisite.

## Acceptance

- `uv run pytest helix_fhir_client_sdk/ tests/` and `uv run mypy helix_fhir_client_sdk/` pass on Python 3.12.
- `byte_identical_json(True)` output equals the legacy oracle byte for byte over the fixtures.
- Hash continuity test passes against constants captured on pre-upgrade `main`.
- No `orjson` type is reachable from the public error surface.
- Before and after benchmark numbers are in the PR description.
- Labels: `type:feature`, the risk label the classifier assigns, `semver:major`.

## Risks to watch in review

- A response constructor or `from_response` that drops the flag (mitigated by the enumeration test in Phase 2).
- A hash site accidentally forwarded the client flag (continuity test catches it).
- The streaming parser change altering which errors consumers see; read consumers before choosing raise versus report.
- Rebase conflicts with #299 and #300 on `json_helpers.py`, `fhir_get_response_factory.py`, `fhir_merge_resources_mixin.py` and shared test files.

## Status (2026-11-22)

Built on `IQ-BAI-1960-orjson-impl` (stacked on #298): phases 1 to 6, the README section, flag and
streaming-parser tests, and the benchmark. Unit suite, `tests` and `tests_integration` pass in the dev container.

Deviations and findings:
- Phase 0 oracle: the byte-identical test compares against `json.dumps(..., cls=FhirJSONEncoder)` directly instead of a copied module, since the old code was exactly that call.
- The NaN hash fixture is pinned to the `compressedfhir` 5.0.0 value: 5.0.0 drops NaN keys in both modes, so `raw_hash` for a NaN-bearing resource changes with the upgrade (recorded in the ADR).
- The mock-server merge tests now expect compact request bodies.

Not done: event-loop stall and GIL re-check on 3.12, cProfile on the Provider New workload, the fhir-server contract test (needs `fhir-server#2775` deployed), the full consumer audit, and the version numbers.
