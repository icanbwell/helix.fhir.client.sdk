# fix_fhir_bundle.py

Prepares a FHIR Bundle (or single resource) for merging to the bwell FHIR server by automatically applying the fixes required to pass merge validation.

## Requirements

- Python 3.9+
- No required dependencies — the script uses the standard library only.
- **Optional:** `fhirschemapy` enables FHIR R4B structural schema validation. If installed, each resource is validated against the R4B schema and structural errors (missing required fields, invalid enum values) are reported alongside the other checks.

```bash
pip install fhirschemapy
```

## Usage

```
python -m helix_fhir_client_sdk.fixers.fix_fhir_bundle \
    --input <PATH> \
    --output <PATH> \
    [--meta-source <URL>] \
    [--owner <CODE>] \
    [--access <CODE>] \
    [--source-assigning-authority <CODE>] \
    [--patient-id <ID>] \
    [--dry-run]
```

## Parameters

| Parameter | Short | Required | Description |
|-----------|-------|----------|-------------|
| `--input` | `-i` | Yes | Path to the input FHIR JSON file (Bundle, Parameters, or single resource). |
| `--output` | `-O` | Yes | Path to write the fixed JSON. Use `-` to write to stdout. |
| `--meta-source` | `-s` | Recommended | URL to set as `meta.source` on every resource that is missing it. Required by the server in production. |
| `--owner` | `-o` | Recommended | Code for the owner security tag (`https://www.icanbwell.com/owner`). Also used as the default value for `--access` and `--source-assigning-authority`. |
| `--access` | `-c` | No | Code for the access security tag (`https://www.icanbwell.com/access`). Defaults to `--owner` if not specified. |
| `--source-assigning-authority` | `-a` | No | Code for the sourceAssigningAuthority tag (`https://www.icanbwell.com/sourceAssigningAuthority`). Added to every top-level resource. For non-UUID ids, satisfies the id-format requirement. Defaults to `--owner` when needed. |
| `--patient-id` | `-p` | No | New ID to assign to the Patient resource. The Patient resource's `id` field is set to this value and all `Patient/<old-id>` references throughout the payload are rewritten to `Patient/<new-id>`. Applied before other fixes so the updated references are validated correctly. |
| `--dry-run` | | No | Print changes and errors to stderr without writing any output. Exit code is still 0 (success) or 1 (unfixable issues). |

## What the script fixes

The script applies these changes to every resource in the input:

| Issue | Auto-fixed? | How |
|-------|-------------|-----|
| Missing `meta.source` | Yes | Set from `--meta-source` |
| Missing owner security tag | Yes | Added from `--owner` |
| Multiple owner security tags | Yes | Keeps the first; removes duplicates |
| Missing access security tag | Yes | Added from `--access` (or `--owner`) |
| Missing sourceAssigningAuthority tag | Yes | Added from `--source-assigning-authority` when provided |
| Security tags with null/empty `system` or `code` | Yes | Removed |
| Missing `id` | Yes | Random UUID v4 generated |
| Non-UUID `id` with no owner or sourceAssigningAuthority tag | Yes | sourceAssigningAuthority tag added from `--source-assigning-authority` (or `--owner`) |
| `id` contains a pipe character (`\|`) | **No** | Reported as an error — remove the pipe manually and set `--source-assigning-authority` to the portion that was after it |
| Invalid reference format | **No** | Reported as an error — references must be `#contained`, `https://...`, or `ResourceType/id` |
| FHIR R4 schema violations (requires fhirschemapy) | **No** | Reported as errors |

## Nested resources

The script recurses into the full resource tree:

- **`Bundle.entry[].resource`** — each entry's resource is processed with the full set of fixes.
- **Nested Bundles** — if an entry's resource is itself a Bundle, its entries are also fixed recursively.
- **`resource.contained[]`** — contained resources are fixed for `id` and references only. They do not require `meta.source` or security tags because they are submitted and validated as part of their parent resource, not independently.

## Output

Progress and errors are written to **stderr**. The fixed JSON is written to **stdout** or the `--output` file.

Each resource is listed with a `+` prefix for applied fixes and a `!` prefix for unfixable issues:

```
[1] Patient/pat-1
  + set meta.source = 'https://example.org'
  + added owner tag (code='my-org')
  + added access tag (code='my-org')
  ! id contains a pipe character '|': 'pat|001' — remove the pipe and set
    --source-assigning-authority to the portion after it

Summary: 1 top-level resource(s), 3 fix(es) applied, 1 unfixable issue(s).
```

**Exit codes:**
- `0` — all resources fixed with no remaining issues
- `1` — one or more unfixable issues remain (output is still written)

## Examples

### Basic: fix a bundle and write to a new file

```bash
python -m helix_fhir_client_sdk.fixers.fix_fhir_bundle \
    --input bundle.json \
    --output fixed.json \
    --meta-source https://example.org/fhir \
    --owner my-org
```

### With all security tags

```bash
python -m helix_fhir_client_sdk.fixers.fix_fhir_bundle \
    --input bundle.json \
    --output fixed.json \
    --meta-source https://example.org/fhir \
    --owner my-org \
    --access my-org \
    --source-assigning-authority my-org
```

### Dry run: see what would change without writing output

```bash
python -m helix_fhir_client_sdk.fixers.fix_fhir_bundle \
    --input bundle.json \
    --output fixed.json \
    --meta-source https://example.org/fhir \
    --owner my-org \
    --dry-run
```

### Write fixed output to stdout

```bash
python -m helix_fhir_client_sdk.fixers.fix_fhir_bundle \
    --input bundle.json \
    --output - \
    --meta-source https://example.org/fhir \
    --owner my-org
```

### Use in a pipeline (check exit code)

```bash
python -m helix_fhir_client_sdk.fixers.fix_fhir_bundle \
    --input bundle.json \
    --output fixed.json \
    --meta-source https://example.org/fhir \
    --owner my-org

if [ $? -eq 0 ]; then
    echo "Ready to merge"
else
    echo "Manual fixes needed — check stderr output"
fi
```

## Common scenarios

### IDs in `source|id` format

Some systems produce ids like `ehr-system|patient-001`. The server rejects ids containing a pipe. Split these before running the script:

1. Use the portion after the pipe as the `id` field value: `patient-001`
2. Pass the portion before the pipe as `--source-assigning-authority`: `ehr-system`

The server will then deterministically generate a UUID from `patient-001|ehr-system` for internal storage.

### Resources already have `meta.source`

If a resource already has `meta.source` set, the script leaves it unchanged. `--meta-source` only fills in the field when it is missing.

### Owner tag already present

If a resource already has exactly one owner tag, it is left unchanged. If it has multiple owner tags, the script keeps the first and removes the rest.

### Single resource (not a bundle)

The script accepts a single FHIR resource JSON directly — it does not need to be wrapped in a Bundle:

```bash
python -m helix_fhir_client_sdk.fixers.fix_fhir_bundle \
    --input patient.json \
    --output fixed_patient.json \
    --meta-source https://example.org/fhir \
    --owner my-org
```

## Related

- Merge validation spec — the full list of checks the server runs during `$merge`
