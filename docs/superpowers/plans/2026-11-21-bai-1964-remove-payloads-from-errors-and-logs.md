# Remove payloads from error strings and logs (BAI-1964)

Jira: BAI-1964. Found during the independent review of the orjson ADR (BAI-1960, PR #297). These sites exist on `main` and are not caused by the orjson work. This document is the plan only; no code changes are in this PR.

## Problem

Org policy: no PHI or PII in logs, exception messages or other diagnostics. Fourteen places put a whole FHIR payload or response body into an error string, a log line or an exception message, and two more put the raw token response (a credential) into a log line and an exception message. A FHIR resource or Bundle can carry PHI, and these strings end up in logs, traces and error reports.

## Sites (line numbers from `origin/main`, recheck before editing)

| # | File | Line | What leaks |
|---|---|---|---|
| 1 | `helix_fhir_client_sdk/responses/get/fhir_get_response_factory.py` | 60 | `error = f"Error parsing response: {response_text}: {e}"` puts the whole response body in the error. This string becomes `FhirGetErrorResponse.error`, which callers can read. |
| 2 | `helix_fhir_client_sdk/responses/get/fhir_get_list_by_resource_type_response.py` | 287 | `assert resource_type, f"No resourceType in {json.dumps(resource)}"` dumps the resource into the assertion message. |
| 3 | `helix_fhir_client_sdk/fhir_merge_resources_mixin.py` | 469 | `self._logger.error(Exception(f"... for bundle: {bundle.json()} ..."))` logs the whole Bundle. |
| 4 | `helix_fhir_client_sdk/fhir_merge_resources_mixin.py` | 696 | the same message with `{resources_to_merge.json()}`. |
| 5 | `helix_fhir_client_sdk/responses/fhir_get_response.py` | 420 | `raise Exception(f"Could not get resourceType and id from resources: {resources.json()}")` puts all resources in the exception text. |
| 6 | `helix_fhir_client_sdk/responses/fhir_get_response.py` | 316 | `__repr__` returns `json.dumps(self.to_dict())`, so any `repr(response)`, f-string, log or debugger display dumps the response. |
| 7 | `helix_fhir_client_sdk/fhir_merge_mixin.py` | 311 | `f"Assertion: FHIR send failed: {str(e)} for resource: {json_data_list}. "` logs the whole input list through `self._logger.error(Exception(...))`. |
| 8 | `helix_fhir_client_sdk/responses/get/fhir_get_list_by_resource_type_response.py` | 184 | `message="Error parsing response: " + responses + ...` puts the response text in a `FhirGetException`, and the same call also sets `json_data=responses` and `response_text=responses`. |
| 9 | `helix_fhir_client_sdk/responses/get/fhir_get_list_response.py` | 153 | `raise Exception(f"Could not get resources from: {response_text}") from e` puts the response body in the exception. |
| 10 | `helix_fhir_client_sdk/responses/get/fhir_get_list_response.py` | 173 | `raise Exception(f"Could not get bundle entries from: {self._resources}") from e` puts the resources in the exception. |
| 11 | `helix_fhir_client_sdk/responses/get/fhir_get_single_response.py` | 169 | `raise Exception(f"Could not get bundle entries from: {self._resource}") from e` puts the resource in the exception. |
| 12 | `helix_fhir_client_sdk/responses/get/fhir_get_single_response.py` | 206 | `raise Exception(f"Could not get resources from: {responses}") from e` puts the response text in the exception. |
| 13 | `helix_fhir_client_sdk/responses/get/fhir_get_bundle_response.py` | 276 | `raise Exception(f"Could not get bundle entries from: {responses}") from e` puts the response text in the exception. |
| 14 | `helix_fhir_client_sdk/responses/get/fhir_get_bundle_response.py` | 325 | `raise Exception(f"Could not get parse json from: {bundle}") from e` puts the bundle in the exception. |
| 15 | `helix_fhir_client_sdk/fhir_auth_mixin.py` | 291, 292 | logs `No token found in {token_text}` and raises `No access token found in {token_text}`. Credential leak, not PHI. |
| 16 | `helix_fhir_client_sdk/fhir_auth_mixin.py` | 297, 298 | logs `No token found in {token_json}` and raises `No access token found in {token_json}`. Credential leak, not PHI. |

## Related, to audit (not confirmed leaks)

`fhir_merge_resources_mixin.py:394` and `:621` pass `json.dumps([r.to_dict() for r in responses] + [e.to_dict() for e in errors])` as the `error=` value. `FhirMergeResourceResponseEntry.to_dict()` carries ids, `message`, `issue` and `error` (server text), not the resource body, so this is not obviously a payload leak. Check whether the server text in `message`/`issue` can echo submitted data; if it can, treat these like the sites above.

## Side effects an implementer must decide on

- **The payload is still on the response object.** Removing the body from the `error` string (site 1) does not remove it from the response: `FhirGetErrorResponse` stores `response_text` in `_error_text` (`fhir_get_error_response.py:87`) and `get_response_text()` returns it. Decide whether that is accepted (the caller asked for the response) or in scope. The plan assumes it is accepted and out of scope, because the caller owns what it does with the object it requested; record that decision in the PR.
- **OperationOutcome diagnostics carry the same text.** When `create_operation_outcome_for_error` is true, `error` flows into `FhirBundleAppender.create_operation_outcome_resource(error=...)` (see `fhir_get_error_response.py` around line 231), so the OperationOutcome currently includes the payload too. Fixing site 1 changes that output; callers that display or store it will see the shorter text.
- **Sites 3, 4 and 7 log `str(e)`.** Fixing site 2 makes the `AssertionError` text safe for that source, but other assertions that reach those `except` blocks are not audited here.

## What to do

1. Before editing, search for callers and tests that read the current text: `git grep -n "Error parsing response"`, `"No resourceType in"`, `"Could not get resourceType"`, `"FHIR send failed"`, `"Could not get resources from"`, `"Could not get bundle entries from"`, `"Could not get parse json from"`, `"No access token found"`. On `main` no test asserts any of these strings (checked), but recheck. Site 1 changes text that is part of the public `error` field, so note the change in the PR and decide the semver label.
2. Replace each payload with metadata that is safe to log:
   - sites 1, 8 and 9 to 14: status, URL path without query values that identify a person, `len(response_text)`, and the parse error `str(e)` (check that `json.JSONDecodeError` text does not echo the input; it reports position only for stdlib `json`, but verify for the parser actually used);
   - sites 2, 5, 8, 9, 10, 11, 12, 13 and 14: resource type, resource `id` where present, and counts;
   - sites 3, 4 and 7: number of resources, resource types, the exception, and the request id; keep `str(e)` only if the server error text is known not to echo the payload;
   - sites 15 and 16: the HTTP status and `len(token_text)`, never the body (the same replacement applies to the log line and the exception);
   - site 6: a short repr such as `FhirGetResponse(status=..., url=..., resource_type=..., total_count=...)` with no `response_text`.
3. Keep exception chaining (`raise ... from e`) so the original cause is still available to a debugger.
4. If a developer needs the payload while debugging, do not add a flag that logs it in production. Point to local debugging only.

## Tests

Use synthetic resources only (no real patient data). For each site, build a resource containing a distinctive marker string (for example `"SYNTHETIC-PAYLOAD-MARKER"` in a name field), trigger the failure, and assert the resulting message, log record or `repr` does not contain the marker while still containing the safe metadata. Use `caplog` for sites 3 and 4.

## Acceptance

- None of the sixteen sites contains payload or token text; tests above pass, and a `git grep` of `helix_fhir_client_sdk/` (excluding tests) for f-strings or concatenations that interpolate `.json()`, `json.dumps(` of a resource, `response_text`, `responses`, `json_data_list`, `bundle`, `self._resource`, `self._resources`, `token_text` or `token_json` into error, log or exception text finds nothing left. Match any f-string or concatenation that interpolates one of those variables, not only `raise Exception(f"...")`.
- `uv run pytest helix_fhir_client_sdk/ -v` and `uv run mypy helix_fhir_client_sdk/` pass.
- The PR states which public strings changed (site 1) and the semver label chosen.

## Not in scope

Other logging in the SDK (the wider audit is tracked in BAI-1970 and must be done alongside or after this plan), and anything in the orjson ADR work (BAI-1960).
