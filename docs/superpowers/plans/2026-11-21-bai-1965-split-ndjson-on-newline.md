# Split NDJSON on "\n" instead of `splitlines()` (BAI-1965)

Jira: BAI-1965. Found during the independent review of the orjson ADR (BAI-1960, PR #297). This is a standalone bug fix, not an orjson prerequisite. This document is the plan only; no code changes are in this PR.

## Problem

`parse_json_or_ndjson` (`helix_fhir_client_sdk/utilities/json_helpers.py:19`) splits an NDJSON response body with `text.splitlines()`. In Python, `str.splitlines()` splits on more than `\n`: it also splits on U+2028, U+2029, U+0085 and the ASCII separators `\x0b`, `\x0c`, `\x1c`-`\x1e`. JSON text escapes the control characters (`\x0b`, `\x0c`, `\x1c`-`\x1e` appear as `\u000b` and so on), so those cannot occur inside a record. U+0085, U+2028 and U+2029 are not control characters below U+0020 and JSON does not require them to be escaped.

fhir-server writes NDJSON with `JSON.stringify(chunk)` followed by `'\n'`
(`src/operations/streaming/resourceWriters/objectSerializedFhirResourceNdJsonWriter.js`, lines 24-26). `JSON.stringify` leaves U+2028, U+2029 and U+0085 unescaped. So a server response in which a record has one of those characters inside a string value is split in the middle of that record by `splitlines()`, each half fails `json.loads`, and the call raises `JSONDecodeError` (reproduced against the current code with a synthetic two-record body; Node's `JSON.stringify` leaving all three characters raw was checked the same way).

This is narrow (it needs one of those three characters inside a string value, for example in a pasted clinical note), but the SDK is the wrong place to mis-split it. The streaming parser (`utilities/ndjson_chunk_streaming_parser.py`, line 25) already splits on `"\n"` and is not affected.

`parse_json_or_ndjson` is called from:
- `helix_fhir_client_sdk/fhir_merge_mixin.py:227`
- `helix_fhir_client_sdk/fhir_merge_resources_mixin.py:172`
- `helix_fhir_client_sdk/responses/merge/fhir_merge_resource_response_entry.py:115`

(Line numbers from `origin/main`, recheck before editing.)

## What to do

1. In `json_helpers.py`, change the fallback to split on `"\n"` only:
   `[json.loads(line) for line in text.split("\n") if line.strip()]`.
   A trailing `\r` (from `\r\n`) is whitespace, so `json.loads` accepts it; the `line.strip()` filter still skips blank lines.
2. Update the three test sites that split a body with `splitlines()` to split on `"\n"` too, so they are robust when a body contains raw U+2028 (which will happen once request bodies stop escaping non-ASCII, see BAI-1960):
   - `helix_fhir_client_sdk/test/test_merge_streaming_request_body.py:34` and `:191`
   - `helix_fhir_client_sdk/test/test_merge_content_type_is_source_of_truth.py:90`
3. Do not change `ndjson_chunk_streaming_parser.py`.

## Tests

Extend `helix_fhir_client_sdk/utilities/test/test_parse_json_or_ndjson.py` (it already covers a single object, an array, newline-delimited, blank lines and invalid input). Use synthetic text only. Parameterize over the characters U+2028, U+2029 and U+0085: build two records whose string values contain the character, serialize each with `json.dumps(record, ensure_ascii=False)` so the character is raw, join with `"\n"`, and assert `parse_json_or_ndjson` returns the two records unchanged. Add a case with `\r\n` line endings. Keep the existing tests passing.

## Acceptance

- The new parameterized tests fail on `main` and pass with the change.
- `uv run pytest helix_fhir_client_sdk/ -v` and `uv run mypy helix_fhir_client_sdk/` pass.
- No behavior change for ASCII-escaped bodies.
- Semver: patch (bug fix, no public API change).

## Not in scope

The orjson work (BAI-1960), and the fhir-server chunk-boundary decoding fix (`icanbwell/fhir-server#2775`, a separate repository).
