# Use orjson for the SDK's own JSON parsing and writing, with compact text by default

* Status: proposed
* Deciders: Imran Qureshi
* Date: 2026-11-21
* Jira: TBD (ticket and `XX-PROJ-123` branch name required before commit)

## Context and Problem Statement

The SDK moves FHIR Bundles and resource lists through the standard library `json` on every
request: it parses each response, re-serializes resources for `$merge` bodies, and re-parses and
re-serializes entries to compute cache hashes. `json` holds the GIL, so for a large Bundle every
other coroutine on the event loop waits. On a synthetic Bundle of 10,000 Observations (about 10 MB)
`json.dumps` blocks for 53 ms and `json.loads` for 54 ms (measured, below).

The related package `compressed-fhir` made the same move in PR #31 (ADR 0002 there). This ADR
covers only this repository's own `json` calls.

Repo state analysed: `helix.fhir.client.sdk@f6e8e34` (`main`), 2026-11-21. This work follows the
separate PR that upgrades `compressedfhir` to 5.0.0 (see Sequencing).

### Where the SDK uses `json`

`grep -rnE "json\.(load|loads|dump|dumps)\b"` over `*.py`: library code has 48 call lines in 21
files (21 `loads`, 29 `dumps`). There is no `json.dump`. The 21 `json.load` calls are all tests
reading fixture files. Tests add 82 `loads` and 196 `dumps` (all scopes, repo-wide).

| Role | Sites | Hot? |
|---|---|---|
| Parse response text | `fhir_response_processor.py:421` (every GET page, only to read the `next` link), `fhir_get_response.py:308`, `fhir_get_response_factory.py:58`, `retryable_aiohttp_response.py:102`, `fhir_get_error_response.py:248`, `request_queue_mixin.py:371`, `fhir_delete_mixin.py:157` | yes |
| Streaming NDJSON parse | `ndjson_chunk_streaming_parser.py:35` (one `loads` per line), `json_helpers.py:17-19` (`parse_json_or_ndjson`) | yes |
| Build `$merge` / patch bodies | `fhir_merge_mixin.py:59,81,152,174,178,180,297`, `fhir_patch_mixin.py:71,129` | yes |
| Build response text | `fhir_response_processor.py:517-526,675`, `fhir_get_list_response.py:270`, `fhir_get_list_by_resource_type_response.py:274`, `fhir_get_error_response.py:206` (the last three pass `cls=FhirJSONEncoder`) | yes |
| Cache-hash normalization: `json.dumps(json.loads(resource.json()), sort_keys=True)` then SHA-256 | `simulated_graph_processor_mixin.py:1521,1812`, `fhir_get_bundle_response.py:364` | yes, but see Further decisions |
| Error and diagnostic text | `fhir_merge_mixin.py:241,266,302`, `fhir_merge_resources_mixin.py:394,621`, `fhir_patch_mixin.py:121,130`, `fhir_bundle_appender.py:180`, `fhir_get_response.py:316` | no |
| Auth | `fhir_auth_mixin.py:200,238,294` | no (tiny payloads) |
| Debug and CLI | `dictionary_writer.py:40` (`default=json_serial`), `fix_fhir_bundle.py:597,655` (`indent=2`) | no |

orjson 3.11.9 is already in `uv.lock` (line 1565) because `compressedfhir` 3.0.5 depends on it
(`uv.lock:580`). This SDK does not declare it.

### Measured speed

Synthetic Observation Bundles (no PHI), `timeit` best of 5, Python 3.13.12, orjson 3.11.9, arm64
macOS laptop. Ratios are the useful signal; production numbers will differ.

| Operation | 100 entries (~100 KB) | 1,000 (~1 MB) | 10,000 (~10 MB) | Speed-up |
|---|---|---|---|---|
| `dumps` | 0.52 → 0.09 ms | 5.0 → 0.83 ms | 53.1 → 9.6 ms | 5.5-6.1x |
| `dumps(sort_keys=True)` | 0.69 → 0.12 ms | 6.8 → 1.1 ms | 69.9 → 12.7 ms | 5.5-6.1x |
| `loads` (str) | 0.46 → 0.23 ms | 4.6 → 2.5 ms | 54.2 → 33.3 ms | 1.6-2.0x |
| `loads` (bytes) | 0.46 → 0.23 ms | 4.8 → 2.6 ms | 56.2 → 33.1 ms | 1.7-2.0x |
| NDJSON, 1,000 per-line `loads` | | 5.4 → 2.6 ms | | 2.0x |

Compact output was 7.8% smaller on the 1,000-entry Bundle (1,028,045 → 948,039 bytes; mostly ASCII).

These are the gains from swapping the library only. compressed-fhir's 7 to 10x came from also
removing double decodes and repeated pruning, so do not carry those multiples over. Serialization
is where the gain is (about 6x); parsing is about 2x. The end-to-end effect on a real request is
**unproven**: the savings are milliseconds per large page against network time in the hundreds of
milliseconds. The realistic benefit is less event-loop blocking during parallel graph fan-out.

## Decision Drivers

* Large speedup on the SDK's own parse and dump paths without changing what FHIR servers see.
* orjson is already installed for every consumer, so there is no new package in practice.
* Callers that depend on the exact old text need a simple way to keep it (the pattern PR #31 chose).
* A change to default output is breaking and must be versioned as such.
* Cache hashes that callers may have persisted must not silently change.

## Considered Options

1. Keep the standard library `json` (status quo).
2. Replace `json` with orjson at every call site, exact stdlib text unavailable.
3. Use orjson on the hot paths behind one internal module; compact text by default; the exact
   previous text available through an opt-in client option; stdlib kept on the paths listed below.
4. Use `compressedfhir`'s `FhirClientJsonHelpers.orjson_dumps/orjson_loads` instead of our own module.
5. Add another fast JSON library (ujson, msgspec, simdjson).

## Decision Outcome

Chosen option: **3**, released as a **major** version because the default serialized text,
NaN handling and big-int parse behavior are visible to callers. The target version number is open.

* Option 1 leaves about 6x serialization headroom unused.
* Option 2 touches 21 files, changes every cache hash and has no way back for callers that need the
  old text.
* Option 4 couples a core concern to a transitive package's helper API. We depend on orjson directly.
* Option 5 adds a dependency when orjson is already installed. Not evaluated further.
* orjson is the default and `FhirClient.byte_identical_json()` restores the previous text,
  following `json(byte_identical=True)` in compressed-fhir PR #31.

### Further decisions

* **One internal module.** `helix_fhir_client_sdk/utilities/fast_json.py` exposes
  `dumps_str(obj, *, byte_identical=False) -> str` and `loads(text: str | bytes, *, byte_identical=False)`
  plus one `default` hook equivalent to `FhirJSONEncoder`. Call sites depend on this module, not on
  orjson, so a later vendor change touches one file. Functions only, no module state; the flag is an
  argument. Return type stays `str` (orjson returns `bytes`).
* **Guarded parse.** `loads` calls orjson and falls back to the standard library for anything orjson
  handles differently. Verified here: `orjson.loads` turns `123456789012345678901234567890` into the
  float `1.2345678901234568e+29` with no error, and rejects `NaN` that stdlib accepts. PR #31 uses
  the same guard (`parse_json_natively`) for NaN/Infinity, integers beyond 64 bits and lone surrogates.
  `orjson.JSONDecodeError` subclasses both `ValueError` and `json.JSONDecodeError` (verified), so the
  existing `except json.JSONDecodeError` handlers keep working.
* **Guarded write.** `dumps_str` falls back to stdlib where orjson raises `TypeError` (verified:
  integers beyond 64 bits, int keys, `set`, lone surrogates). `datetime`, `UUID`, `Enum` and
  dataclasses are handled natively; `Decimal`, `bytes`, `Path` and objects with `to_dict` or
  `__dict__` go through the `default` hook. Every fallback is logged at debug level, never with
  payload content.
* **Cache hashing stays on the standard library.** The hash input is the serialized text, and
  orjson text differs from stdlib text (verified: hashes differ). `raw_hash` is compared against
  `cache_map` values that callers may have persisted from earlier versions, so switching would make
  every cached entry compare unequal (cache churn, not data loss). Sites:
  `simulated_graph_processor_mixin.py:1521,1812`, `fhir_get_bundle_response.py:364`. This holds in
  both default and `byte_identical_json(True)` modes, so one resource never hashes differently per
  client. A regression test pins a fixed resource's hash.
* **NDJSON framing fix is a prerequisite.** orjson does not escape U+2028 or U+0085, and
  `parse_json_or_ndjson` uses `text.splitlines()` (`json_helpers.py:19`). Verified: a record containing
  U+2028 splits into 2 lines with orjson output and 1 with stdlib output. The `$merge` NDJSON path
  joins records with `"\n"` (`fhir_merge_mixin.py:178`), so a resource containing U+2028 would be cut
  mid-record. Change `splitlines()` to `split("\n")` before any NDJSON dump moves to orjson.
  `ndjson_chunk_streaming_parser.py` already splits on `"\n"`.
* **Paths that stay on stdlib:** the cache-hash paths above; `dictionary_writer.py` and
  `fix_fhir_bundle.py` (debug and CLI, rely on `default=str` and `indent`); `fhir_auth_mixin.py`
  (tiny payloads, no benefit).
* **Client option for the old text.** `FhirClient.byte_identical_json(use: bool = True) -> FhirClient`
  following the fluent setters `use_data_streaming` (`fhir_client.py:386`), `content_type` (`:435`)
  and `compress` (`:496`). Field `self._byte_identical_json: bool = False` beside `_content_type`
  (`:124`). It must also be copied in the clone code (`fhir_client.py:988-1016`), or clones silently
  revert to orjson. The name states the contract ("same bytes as before"), not the library; a
  `json_backend` enum was rejected so the name survives a vendor change. Kept indefinitely, as in PR #31.

  | Behavior | Default | `byte_identical_json(True)` |
  |---|---|---|
  | Separators | compact `,` `:` | `, ` `: ` |
  | Non-ASCII | raw UTF-8 | `\uXXXX` escapes |
  | NaN / Infinity on dump | `null` | stdlib literals |
  | NaN / Infinity on parse | stdlib fallback, same either way | stdlib |
  | U+2028 in an NDJSON body | raw (hence the framing fix) | escaped |

* **Sequencing: this PR comes after the `compressedfhir` 5.0.0 upgrade PR.** The upgrade is a
  separate PR that merges first; this ADR does not cover it. This PR assumes `compressedfhir` 5.0.0 is
  already the locked version (today the repo is `>=3.0.5`, locked 3.0.5, and 5.0.0 is not on PyPI;
  PyPI's latest is 4.0.0, checked 2026-11-21). Consequences:
  * `byte_identical_json` is forwarded to every `compressedfhir` text call as `.json(byte_identical=...)`,
    which 5.0.0 provides: `fhir_merge_resources_mixin.py:56-63,546-552,726,752`,
    `fhir_update_mixin.py:36,54`, `fhir_get_single_response.py:220`, `fhir_get_list_response.py:246`,
    `fhir_get_bundle_response.py:424`. With the default, SDK-built and `compressedfhir`-built text are
    both compact orjson text, so merge bodies are consistent.
  * **Two major releases (decided).** The `compressedfhir` 5.0.0 upgrade ships as its own major; this
    work ships as a second major. `byte_identical_json` is introduced only in the second major.
    Accepted consequence: clients on the first major get compact `compressedfhir` text with no
    SDK option to restore the old text; they must wait for the second major or pin the earlier
    release. The upgrade PR's description and release notes should say so.
  * "The previous text" in the table above means **stdlib text for everything the SDK emits**
    (decided), including what `compressedfhir` writes via `byte_identical=True`. It is the SDK's
    output before either major, not the text of the first major with defaults. That definition does
    not depend on release history, and matches `byte_identical` in PR #31.
  * The upgrade PR owns these checks, which this PR relies on being done: `raw_dict()` returning
    `Dict` rather than `OrderedDict` (`simulated_graph_processor_mixin.py:1199`; unproven), whether the
    `cls=FhirJSONEncoder` sites can go (unproven), NaN becoming `null` in `dict()`, and that the hash
    path is unchanged (stdlib normalization hides text differences; only NaN→`null` could change a
    hash).
  * If the upgrade PR slips, this PR cannot forward the flag (3.0.5 has no `byte_identical`). Do not
    merge this PR ahead of it.

### Consequences

* Good: about 6x faster `dumps` and about 2x faster `loads` on the hot paths in isolation; about 8%
  smaller request bodies; shorter event-loop stalls on large pages; an explicit way back to the old
  text.
* Bad: default request and response text changes; callers that assert on or persist exact text must
  call `byte_identical_json()`; NaN is written as `null` by default; a plain `Enum` or `UUID` is
  accepted where stdlib's `default` hook would previously have been consulted; tests that assert
  exact body strings must compare parsed JSON instead.
* Risk: gain smaller than expected end to end (see Context). Do not advertise an end-to-end speedup
  until profiled.
* Public contract: return types stay `str`. Released as a major version with a README upgrade
  section listing the differences. A published major cannot be unpublished, so undoing this needs a
  follow-up release.
* Dependency: declare `orjson>=3.11.9` in `pyproject.toml` (a direct dependency now, not transitive).
  The `exclude-newer = "2 days"` setting applies.
* Not applicable: tenancy (no persistence or query changes), PHI (benchmarks use synthetic data and
  no payloads are logged), event schemas, and AWS, IAM, FHIR scope or public endpoint changes.

### Tests

Parameterized over both modes where behavior differs:

1. `byte_identical_json(True)` output equals the previous major's output byte for byte over
   fixtures (ASCII, non-ASCII, U+2028, floats, `Decimal`, `datetime`), using a verbatim copy of the
   old logic as the oracle (the approach PR #31 used).
2. Default output parses to a value equal to the `byte_identical_json(True)` output.
3. `fast_json.loads`: big ints stay ints; NaN follows stdlib; invalid JSON raises a
   `json.JSONDecodeError`.
4. NDJSON round trip with U+2028 and U+0085 through merge dump and `parse_json_or_ndjson`.
5. Cloning a client preserves the flag, and the flag reaches the `compressedfhir`
   `.json(byte_identical=...)` call at every site listed under Sequencing (assert on the sent body).
6. A fixed resource hashes identically in both modes.
7. Existing suite passes; exact-text assertions are rewritten to compare parsed JSON, as
   `test_merge_streaming_request_body.py` already does.
8. Extend `tests/async/test_benchmark_merge.py` (pytest-benchmark is a dev dependency) for
   before/after numbers, and run cProfile on a representative graph traversal to settle the
   end-to-end claim.

### Rollout

One PR per role group (parse, NDJSON, request build, response build), each independently revertable
and labelled with risk, type and semver. The phases can sit on `main` unreleased and ship together as
one major version (the second major, after the `compressedfhir` upgrade) so consumers see a single
breaking upgrade from this work.

### Open items

| Item | Owner | Status |
|---|---|---|
| Jira ticket and branch name | Imran | open |
| Target major version number and release date (`VERSION` is the placeholder `0.0.1`) | Imran | open |
| Upgrade PR for `compressedfhir` 5.0.0: link it here; it must merge first (5.0.0 not yet released) | Imran | open |
| Version numbers for the two majors (the upgrade major, then this one) | Imran | open |
| End-to-end share of wall-clock spent in JSON on a real graph or merge workload | Imran | unproven |
| orjson listed in `icanbwell/.github/policies/approved-tech.yaml` | Imran | checked 2026-11-21: **not listed**. Libraries are catalog-only, so this does not block; chosen because it is already installed through `compressedfhir` and measured about 6x faster `dumps` |
| Wheel availability for the Docker base image (musl) | Imran | unproven |
| Prior-art search in Confluence (Approved) and `gh search code --owner icanbwell orjson`; compressed-fhir PR #31 was supplied, not found by search | Imran | partial |
| Independent `ea-tech-design-review` of this ADR | Imran | not run |
| Tell the PR #31 author its consumer survey lists this repo at `>=1.0.13,<3` locked 1.0.13, but `main` is `>=3.0.5` locked 3.0.5 | Imran | open |

## References

* compressed-fhir PR #31 and its `adrs/0002-faster-json-with-orjson.md` (branch `IQ-BAI-1955`, open
  at the time of writing): the `byte_identical` option, the guarded parse, the NDJSON and hash
  lessons.
* `uv.lock:580,1565`: orjson 3.11.9 via `compressedfhir` 3.0.5.
* Benchmark: synthetic Bundles, `scratchpad/bench.py` (not committed).
