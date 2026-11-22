# Remove payloads from error strings and logs (BAI-1964)

Jira: BAI-1964. Found during the independent review of the orjson ADR (BAI-1960, PR #297). These sites exist on `main` and are not caused by the orjson work. This document is the plan only; no code changes are in this PR.

## Problem

Org policy: no PHI or PII in logs, exception messages or other diagnostics. Six places put a whole FHIR payload or response body into an error string, a log line or an exception message. A FHIR resource or Bundle can carry PHI, and these strings end up in logs, traces and error reports.

## Sites (line numbers from `origin/main`, recheck before editing)

| # | File | Line | What leaks |
|---|---|---|---|
| 1 | `helix_fhir_client_sdk/responses/get/fhir_get_response_factory.py` | 60 | `error = f"Error parsing response: {response_text}: {e}"` puts the whole response body in the error. This string becomes `FhirGetErrorResponse.error`, which callers can read. |
| 2 | `helix_fhir_client_sdk/responses/get/fhir_get_list_by_resource_type_response.py` | 287 | `assert resource_type, f"No resourceType in {json.dumps(resource)}"` dumps the resource into the assertion message. |
| 3 | `helix_fhir_client_sdk/fhir_merge_resources_mixin.py` | 469 | `self._logger.error(Exception(f"... for bundle: {bundle.json()} ..."))` logs the whole Bundle. |
| 4 | `helix_fhir_client_sdk/fhir_merge_resources_mixin.py` | 696 | the same message with `{resources_to_merge.json()}`. |
| 5 | `helix_fhir_client_sdk/responses/fhir_get_response.py` | 420 | `raise Exception(f"Could not get resourceType and id from resources: {resources.json()}")` puts all resources in the exception text. |
| 6 | `helix_fhir_client_sdk/responses/fhir_get_response.py` | 316 | `__repr__` returns `json.dumps(self.to_dict())`, so any `repr(response)`, f-string, log or debugger display dumps the response. |

## What to do

1. Before editing, search for callers and tests that read the current text: `git grep -n "Error parsing response"`, `"No resourceType in"`, `"Could not get resourceType"`, `"FHIR send failed"`. Site 1 changes text that is part of the public `error` field, so note the change in the PR and decide the semver label.
2. Replace each payload with metadata that is safe to log:
   - site 1: status, URL path without query values that identify a person, `len(response_text)`, and the parse error `str(e)` (check that `json.JSONDecodeError` text does not echo the input; it reports position only for stdlib `json`, but verify for the parser actually used);
   - sites 2 and 5: resource type, resource `id` where present, and counts;
   - sites 3 and 4: number of resources, resource types, the exception, and the request id; keep `str(e)` only if the server error text is known not to echo the payload;
   - site 6: a short repr such as `FhirGetResponse(status=..., url=..., resource_type=..., total_count=...)` with no `response_text`.
3. Keep exception chaining (`raise ... from e`) so the original cause is still available to a debugger.
4. If a developer needs the payload while debugging, do not add a flag that logs it in production. Point to local debugging only.

## Tests

Use synthetic resources only (no real patient data). For each site, build a resource containing a distinctive marker string (for example `"SYNTHETIC-PAYLOAD-MARKER"` in a name field), trigger the failure, and assert the resulting message, log record or `repr` does not contain the marker while still containing the safe metadata. Use `caplog` for sites 3 and 4.

## Acceptance

- None of the six messages contains payload text; tests above pass.
- `uv run pytest helix_fhir_client_sdk/ -v` and `uv run mypy helix_fhir_client_sdk/` pass.
- The PR states which public strings changed (site 1) and the semver label chosen.

## Not in scope

Other logging in the SDK (a wider audit can be a separate ticket), and anything in the orjson ADR work (BAI-1960).
