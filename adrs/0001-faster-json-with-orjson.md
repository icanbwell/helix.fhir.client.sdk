# Use orjson for the SDK's own JSON parsing and writing, with compact text by default

* Status: proposed
* Deciders: Imran Qureshi
* Date: 2026-11-21
* Jira: BAI-1960

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

`grep -rnE "json\.(load|loads|dump|dumps)\b"` over `*.py`: library code has 49 call lines in 21
files (47 once two commented-out lines in `fhir_response_processor.py` are excluded). There is no
`json.dump`. The 21 `json.load` calls are all tests reading fixture files. Tests alone add 61
`loads` and 165 `dumps` (per the independent review of this ADR; the earlier 82 and 196 were
repo-wide totals including library code).

| Role | Sites | Hot? |
|---|---|---|
| Parse response text | `fhir_response_processor.py:421` (every GET page, only to read the `next` link), `fhir_get_response.py:308`, `fhir_get_response_factory.py:58`, `retryable_aiohttp_response.py:102`, `fhir_get_error_response.py:248`, `request_queue_mixin.py:371`, `fhir_delete_mixin.py:157`, `responses/merge/fhir_merge_response_entry_issue.py:55` | yes |
| Streaming NDJSON parse | `ndjson_chunk_streaming_parser.py:35` (one `loads` per line), `json_helpers.py:17-19` (`parse_json_or_ndjson`) | yes |
| Build `$merge` / patch bodies | `fhir_merge_mixin.py:59,81,152,174,178,180,297`, `fhir_patch_mixin.py:71,129` | yes |
| Build response text | `fhir_response_processor.py:517-526,675`, `fhir_get_list_response.py:270`, `fhir_get_list_by_resource_type_response.py:274,287`, `fhir_get_error_response.py:206` (three pass `cls=FhirJSONEncoder`) | yes |
| Cache-hash normalization: `json.dumps(json.loads(resource.json()), sort_keys=True)` then SHA-256 | `simulated_graph_processor_mixin.py:1521,1812`, `fhir_get_bundle_response.py:364` | yes, but see Further decisions |
| Error and diagnostic text | `fhir_merge_mixin.py:241,266,302`, `fhir_merge_resources_mixin.py:394,621`, `fhir_patch_mixin.py:121,130`, `fhir_bundle_appender.py:180`, `fhir_get_response.py:316` | no |
| Auth | `fhir_auth_mixin.py:200,238,294` | no (tiny payloads) |
| Debug and CLI | `dictionary_writer.py:40` (`default=json_serial`), `fix_fhir_bundle.py:597,655` (`indent=2`) | no |

orjson 3.11.9 is already in `uv.lock` (line 1565) because `compressedfhir` 3.0.5 depends on it
(`uv.lock:580`). This SDK does not declare it. `uv.lock` also lists musllinux wheels for it
(`cp312`, x86_64 and aarch64), matching the `python:3.12-alpine3.20` base image.

### Measured speed

Synthetic Observation Bundles (no PHI), `timeit` best of 5, Python 3.13.12, orjson 3.11.9, arm64
macOS laptop. CI and the floor are Python 3.12, so the benchmark must be re-run there (see Tests).
Ratios are the useful signal; production numbers will differ.

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
is where the gain is (about 6x); parsing is about 2x, and only without a guard (see Further
decisions). The end-to-end effect on a real request is **unproven**: the savings are milliseconds
per large page against network time in the hundreds of milliseconds. The realistic benefit is less
event-loop blocking during parallel graph fan-out.

## Decision Drivers

* Large speedup on the SDK's own parse and dump paths without changing the meaning of what FHIR
  servers receive. The bytes do change (compact, raw UTF-8); see Further decisions for the
  fhir-server prerequisite this creates.
* orjson is already installed for every consumer and already declared by other icanbwell repos, so
  there is no new package in practice.
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
6. As option 3, but stdlib text stays the default and orjson text is opt-in (no default change, so
   no major release and no raw-UTF-8 exposure for clients that do not opt in).
7. orjson on write paths only; stdlib on all parse paths.
8. Leave the libraries alone and move large parses off the event loop (`asyncio.to_thread`).

## Decision Outcome

Chosen option: **3**, released as a **major** version because the default serialized text, NaN
handling and big-integer parse behavior are visible to callers. The target version number is open.

* Option 1 leaves about 6x serialization headroom unused.
* Option 2 touches 21 files, changes every cache hash and has no way back for callers that need the
  old text.
* Option 4: `compressedfhir` is a direct dependency (`pyproject.toml:27`), so "transitive" is not the
  reason. The reasons are that `FhirClientJsonHelpers.orjson_loads` prints the error and returns
  `None` on failure (PR #31 `json_helpers.py:195-207`, so parse errors would no longer raise), and
  `orjson_dumps` has no `default` hook. Neither fits the SDK's error handling.
* Option 5 adds a dependency when orjson is already installed. Not evaluated further.
* Option 6 avoids a breaking release. It was not chosen because the default here is deliberately kept
  consistent with `compressedfhir` 5.0.0 and PR #31, which made compact orjson text the default with
  an opt-out, so one flag means the same thing across both packages and clients get the speedup
  without editing code. The cost is a major release and the prerequisites below. This is a
  maintainer decision, not a technical necessity: an opt-in design would work and would remove F1's
  exposure for clients that stay on the default.
* Option 7 was rejected as the whole answer: parsing is the same unguarded swap the maintainers
  chose to accept (see Further decisions), and the gain on parse (about 1.6-2x) is real.
* Option 8 does not reduce CPU, only moves it off the loop; it is compatible with this ADR and can
  be done separately.
* orjson is the default and `FhirClient.byte_identical_json()` restores the previous text,
  following `json(byte_identical=True)` in compressed-fhir PR #31.

### Further decisions

* **One internal module.** `helix_fhir_client_sdk/utilities/fast_json.py` exposes
  `dumps_str(obj, *, byte_identical=False) -> str` and `loads(text: str | bytes, *, byte_identical=False)`
  plus one `default` hook equivalent to `FhirJSONEncoder`. Call sites depend on this module, not on
  orjson, so a later vendor change touches one file. Functions only, no module state; the flag is an
  argument. Return type stays `str` (orjson returns `bytes`).
* **Parse with orjson, no guard (decided).** PR #31 adds a digit-run guard (`parse_json_natively`)
  that falls back to stdlib for big integers. Measured here on a 7.2 MB synthetic Bundle, the guard
  scan costs about 14-15 ms against a saving of about 15 ms (stdlib 39.3 ms, orjson 24.8 ms), and the
  independent review measured it at 54.7 ms on another bundle, so a guarded parse is no faster than
  stdlib. We therefore parse with orjson unguarded and document the differences:

  | Input | stdlib | orjson (default) | Loud or silent |
  |---|---|---|---|
  | Integer below -2^63 or above 2^64-1 | exact `int` | **float** | **silent** |
  | `NaN`, `Infinity`, `1e400` | accepted | `JSONDecodeError` | loud |
  | Nesting deeper than 1024 | accepted | rejected | loud (review, not re-run) |
  | Ordinary floats and integers | same | same (199,951 random literals compared, 0 differences) | n/a |

  The silent case is narrow: FHIR `integer` is 32-bit (R4 datatypes), so only a `decimal` written as
  an integer-valued JSON number of 20 or more digits can hit it. Both libraries already lose
  precision on fractional decimals (the FHIR R4 JSON page notes `2.00` becomes `2`). The SDK's
  `$merge` path parses and re-dumps resources (`fhir_merge_mixin.py:152`), so such a value would be
  rewritten as a float before being sent. This is an accepted, documented difference;
  `byte_identical_json(True)` parses with stdlib and keeps the exact value. Message text of
  `JSONDecodeError` also differs where `str(e)` is surfaced (`fhir_merge_mixin.py:234`,
  `fhir_patch_mixin.py:123`). `orjson.JSONDecodeError` subclasses both `ValueError` and
  `json.JSONDecodeError` (verified), so existing `except json.JSONDecodeError` handlers still catch it.
* **Guarded write.** `dumps_str` falls back to stdlib where orjson raises `TypeError` (verified:
  integers beyond 64 bits, int keys, `set`, lone surrogates). This guard is exception-based and costs
  nothing on the normal path. `datetime`, `UUID`, `Enum` and dataclasses are handled natively;
  `Decimal`, `bytes`, `Path` and objects with `to_dict` or `__dict__` go through the `default` hook.
  Every fallback is logged at debug level, never with payload content, and increments a counter
  (and sets a span attribute on the active OpenTelemetry span; the SDK already uses
  `TRACER.start_as_current_span`), so fallback rates can be seen in production. NaN is written as
  `null` by orjson by default.
* **fhir-server must decode NDJSON chunks correctly first (prerequisite, cross-repo).** orjson and
  `compressedfhir` 5.0.0 write raw UTF-8, where stdlib wrote ASCII-escaped text. fhir-server's
  `NdjsonParser` did `this._buffer += chunk.toString();` per chunk
  (`src/operations/merge/ndJsonParser.js`), so a multi-byte character split across two chunks decodes
  to U+FFFD, `JSON.parse` still succeeds, and corrupted text is persisted. Fix: PR
  `icanbwell/fhir-server#2775` (Jira DCON-6862) decodes with `StringDecoder('utf8')` and has tests
  for 2-, 3- and 4-byte characters split at every interior byte. It must be **merged and deployed**
  before any release that sends raw-UTF-8 NDJSON `$merge` bodies, which includes the `compressedfhir`
  5.0.0 upgrade release as well as this one. Whether real traffic splits mid-character depends on
  network and decompressor chunking and is not measured; the defect is in the code either way.
* **Cache hashing stays on the standard library and pins its input.** The hash input is serialized
  text, and orjson text differs from stdlib text (verified: hashes differ). `raw_hash` is compared
  against `cache_map` values that callers may have persisted (`simulated_graph_processor_mixin.py:76`),
  so switching would make every cached entry compare unequal (cache churn, not data loss). The three
  sites (`simulated_graph_processor_mixin.py:1521,1812`, `fhir_get_bundle_response.py:364`) keep
  stdlib `json` and call `resource.json(byte_identical=True)` with the flag **fixed**, exempt from
  forwarding, so the hash is the same in both client modes. This matters because a resource holding
  NaN produces different `compressedfhir` text in default and exact modes (PR #31 default drops the
  NaN key; the independent review reproduced differing hashes). A regression test pins a fixed
  resource's hash, including a NaN fixture.
* **The NDJSON `splitlines()` fix is standalone, not an orjson prerequisite.**
  `parse_json_or_ndjson` (`json_helpers.py:19`) parses only server responses, and fhir-server writes
  NDJSON with `JSON.stringify`, which leaves U+2028 and U+0085 unescaped, so `text.splitlines()`
  can already mis-split a server response today. The SDK writing raw U+2028 in a request is harmless
  because fhir-server splits on `'\n'`. Ship `splitlines()` → `split("\n")` as its own change, and fix
  `test_merge_streaming_request_body.py:34`, which also uses `body.splitlines()`. Test against
  server-shaped responses containing U+2028. `ndjson_chunk_streaming_parser.py` already splits on `"\n"`.
* **Paths that stay on stdlib:** the cache-hash paths above; `dictionary_writer.py` and
  `fix_fhir_bundle.py` (debug and CLI, rely on `default=str` and `indent`); `fhir_auth_mixin.py`
  (tiny payloads, no benefit).
* **Client option for the old text.** `FhirClient.byte_identical_json(use: bool = True) -> FhirClient`
  following the fluent setters `use_data_streaming` (`fhir_client.py:386`), `content_type` (`:435`)
  and `compress` (`:496`). Field `self._byte_identical_json: bool = False` beside `_content_type`
  (`:124`). The name states the contract ("same bytes as before"), not the library; a `json_backend`
  enum was rejected so the name survives a vendor change. A boolean matches the repo's convention;
  use an enum only if a third mode becomes plausible. Kept indefinitely, as in PR #31.

  | Behavior | Default | `byte_identical_json(True)` |
  |---|---|---|
  | Separators | compact `,` `:` | `, ` `: ` |
  | Non-ASCII | raw UTF-8 | `\uXXXX` escapes |
  | NaN / Infinity on dump | `null` | stdlib literals |
  | NaN / Infinity / big ints on parse | orjson behavior (table above) | stdlib |
  | U+2028 in an NDJSON body | raw | escaped |

* **How the flag reaches every site.** The response-text builders are methods on response objects
  built without the client, so the flag is threaded the way `use_data_streaming` is (about 44
  library lines in 14 files): a field on `FhirClientProtocol`
  (`responses/fhir_client_protocol.py:88` shows the existing pattern), a parameter on
  `FhirResponseProcessor.handle_response` (`responses/fhir_response_processor.py:71`), and a
  keyword-only `byte_identical_json: bool = False` on each response constructor
  (`fhir_get_list_response.py:44-62` and its siblings). The clone code copies each field explicitly
  (`fhir_client.py:974-1038`), so the new field must be added there or clones revert to orjson.
* **Sequencing: this work comes after the `compressedfhir` 5.0.0 upgrade PR, which merges and
  releases first.** That upgrade is a separate PR and is not covered here. This work assumes
  `compressedfhir` 5.0.0 is the locked version (today the repo is `>=3.0.5`, locked 3.0.5; PyPI's
  latest is 4.0.0, checked 2026-11-21). Consequences:
  * **Two major releases (decided).** The upgrade ships as its own major; this work ships as a
    second major, and `byte_identical_json` exists only from the second. Accepted: clients on the
    first major get compact `compressedfhir` text with no SDK option to restore the old text until
    the second major. The upgrade PR's release notes should say so, and should list the fhir-server
    prerequisite above.
  * `byte_identical_json` is forwarded to every `compressedfhir` text call as
    `.json(byte_identical=...)`, which 5.0.0 provides (PR #31 `fhir_bundle.py:220`):
    `fhir_merge_resources_mixin.py:56-63,546-552,726,752`, `fhir_update_mixin.py:36,54`,
    `fhir_get_single_response.py:220`, `fhir_get_list_response.py:246`,
    `fhir_get_bundle_response.py:424`. The hash sites are the exception (fixed flag, above).
  * "The previous text" means **stdlib text for everything the SDK emits** (decided), including what
    `compressedfhir` writes via `byte_identical=True`: the SDK's output before either major.
  * The upgrade PR owns these checks, which this work relies on: `raw_dict()` returning `Dict` rather
    than `OrderedDict` (`simulated_graph_processor_mixin.py:1199`; unproven), whether the
    `cls=FhirJSONEncoder` sites can go (unproven), and NaN handling in `dict()`.
  * If the upgrade PR slips, the flag cannot be forwarded (3.0.5 has no `byte_identical`). Do not
    merge this work ahead of it.
* **Governance (decided).** orjson is not listed in `icanbwell/.github/policies/approved-tech.yaml`
  (checked 2026-11-21). It is already a locked dependency here through `compressedfhir` and is
  already declared by other icanbwell repos (`helix.pipelines`, `helix.personmatching`,
  `mcp-fhir-agent`, `complaint-parser`, `helix-core`, `helix.orchestration`, among others; per the
  independent review's code search). No approval or registry proposal is requested. Recorded for
  reviewers: this repo's `CLAUDE.md` and `AGENTS.md` say an unlisted significant library requires a
  Tech Design Review, while the org registry's catalog tier says unlisted is not a blocker; the
  decision here relies on orjson already being installed and in use.
* **Out of scope but flagged (pre-existing, found in the review).**
  `fhir_get_response_factory.py:60` (`f"Error parsing response: {response_text}: {e}"`) and
  `fhir_get_list_by_resource_type_response.py:287` (`f"No resourceType in {json.dumps(resource)}"`)
  put whole payloads into error strings, which can carry PHI. This ADR touches both files; fix in a
  separate ticket. Also: `fhir_response_processor.py:421` parses the whole response only to read the
  `next` link (a substring check measured about 4 ms against a 39 ms parse); a separate optimization.
  `types-orjson` (dev dependency, `pyproject.toml:63`) should be checked once orjson is a direct
  dependency, since orjson ships its own type stubs.

### Consequences

* Good: about 6x faster `dumps` and about 1.6-2x faster `loads` on the hot paths in isolation; about
  8% smaller request bodies; shorter event-loop stalls on large pages; an explicit way back to the
  old text.
* Bad: default request and response text changes; callers that assert on or persist exact text must
  call `byte_identical_json()`; NaN is written as `null` by default; very large integer-valued
  decimals are silently parsed as floats by default; raw UTF-8 bodies need the fhir-server fix;
  tests that assert exact body strings must compare parsed JSON instead.
* Consumer impact (to verify before the major release; not yet checked). The independent review's
  `gh search code` found repos declaring `helix.fhir.client.sdk` (22 by one count, 13 by another)
  and nine that call `get_response_text`: `ai-health-optimization`, `ai-visit-summary`,
  `fhir-notes-vector-store`, `helix-core`, `helix-event-listener-service`, `helix.pipelines`,
  `iop_databricks`, `mcp-fhir-agent`, `SparkPipelineFramework`. Before release, for each: does it
  assert on or persist exact response or request text, or persisted `raw_hash` values? Record the
  result here as a table (repo, outputs consumed, exact-text dependency, action).
* Risk: gain smaller than expected end to end (see Context). Do not advertise an end-to-end speedup
  until profiled.
* Public contract: return types stay `str`. Released as a major version with a README upgrade
  section listing the differences. A published major cannot be unpublished, so undoing this needs a
  follow-up release.
* Dependency: declare `orjson>=3.11.9` in `pyproject.toml` (a direct dependency now, not transitive).
  The `exclude-newer = "2 days"` setting applies.
* Not applicable: tenancy (no persistence or query changes), PHI in new logging (benchmarks use
  synthetic data and no payloads are logged), event schemas, and AWS, IAM, FHIR scope or public
  endpoint changes.

### Tests

Parameterized over both modes where behavior differs:

1. `byte_identical_json(True)` output equals the previous text byte for byte over fixtures (ASCII,
   non-ASCII, U+2028, floats, `Decimal`, `datetime`), using a verbatim copy of the old logic as the
   oracle (the approach PR #31 used).
2. Default output parses to a value equal to the `byte_identical_json(True)` output, except for the
   documented differences.
3. Parse differences are pinned: a 30-digit integer is a float by default and an exact `int` with the
   flag; `NaN` / `Infinity` / `1e400` raise `json.JSONDecodeError` by default; ordinary numbers are
   equal in both modes.
4. The `split("\n")` NDJSON fix is tested with server-shaped responses containing U+2028 and U+0085.
5. Cloning a client preserves the flag, and the flag reaches every `compressedfhir`
   `.json(byte_identical=...)` call and every response constructor; assert `get_response_text()` in
   both modes and the sent request body.
6. A fixed resource hashes identically in both modes, including a resource containing NaN.
7. Existing suite passes; exact-text assertions are rewritten to compare parsed JSON, as
   `test_merge_streaming_request_body.py` already does.
8. Commit the benchmark (extend `tests/async/test_benchmark_merge.py`; pytest-benchmark is a dev
   dependency) for before/after numbers on Python 3.12 (CI and the floor), and run cProfile on a
   representative graph traversal to settle the end-to-end claim.
9. Contract test against fhir-server `$merge` with a non-ASCII resource split across chunks, once
   `fhir-server#2775` is deployed.

### Rollout

Order: (1) `fhir-server#2775` merged and deployed; (2) the `compressedfhir` 5.0.0 upgrade PR merged
and released as its own major; (3) this work as **one PR covering all phases** (parse, NDJSON,
request build, response build), released as the second major. A single PR keeps `main` from carrying
a breaking phase that an ordinary weekly release would publish (`python-publish.yml` publishes on
every GitHub release; releases 5.0.22 to 5.0.27 shipped between 2026-11-10 and 2026-11-17). The
`split("\n")` fix and the error-string fixes are separate, non-breaking PRs.

### Open items

| Item | Owner | Status |
|---|---|---|
| Link the `compressedfhir` 5.0.0 upgrade PR; it must merge first (5.0.0 not yet released) | Imran | open |
| Version numbers for the two majors | Imran | open |
| `fhir-server#2775` reviewed, merged and deployed | fhir-server owners | open (PR open, CI not checked) |
| Consumer-impact table (Consequences) | Imran | open |
| End-to-end share of wall-clock spent in JSON on a real graph or merge workload | Imran | unproven |
| `compressedfhir` 5.0.0 contract (`raw_dict()` type, `FhirJSONEncoder` removable, NaN in `dict()`) | upgrade PR | unproven |
| Prior-art search in Confluence (Approved); compressed-fhir PR #31 was supplied, not found by search | Imran | partial |
| Tell the PR #31 author its consumer survey lists this repo at `>=1.0.13,<3` locked 1.0.13, but `main` is `>=3.0.5` locked 3.0.5 | Imran | open |
| Tell the `compressedfhir` upgrade PR owner about the raw-UTF-8 prerequisite (`fhir-server#2775`) | Imran | open |
| Separate ticket for PHI in error strings (Further decisions) | Imran | open |

## References

* compressed-fhir PR #31 and its `adrs/0002-faster-json-with-orjson.md` (branch `IQ-BAI-1955`, open
  at the time of writing): the `byte_identical` option, the guard, the NDJSON and hash lessons.
* `icanbwell/fhir-server#2775` (DCON-6862): NDJSON chunk-boundary UTF-8 fix.
* FHIR R4 `datatypes.html` (`integer` is 32-bit; `decimal`) and `json.html` (number precision).
* `uv.lock:580,1565`: orjson 3.11.9 via `compressedfhir` 3.0.5.
* Independent `ea-tech-design-review` of this ADR at `4f7b4e9`: verdict Needs-revision, 10 required
  changes (all addressed or recorded above), 8 suggestions.
