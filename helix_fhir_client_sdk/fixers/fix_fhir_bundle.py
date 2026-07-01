#!/usr/bin/env python3
"""
Prepare a FHIR Bundle (or single resource) for merging to the bwell FHIR server.

Applies every fix required to pass merge validation:
  - Sets meta.source on each resource if missing
  - Removes security tags with null/empty system or code
  - Adds owner security tag if missing or de-duplicates if multiple are present
  - Adds access security tag if missing
  - Adds sourceAssigningAuthority tag if --source-assigning-authority is given
  - Generates a random UUID id for any resource that is missing one
  - Flags ids that contain a pipe character (cannot be auto-fixed)
  - Validates all reference values in the resource tree
  - Recurses into contained[] resources and nested Bundle entries

Contained resources (resource.contained[]) are fixed for id and references only —
they are submitted as part of their parent and are not independently validated for
meta.source or security tags.

If fhirschemapy is installed, each resource is also validated against the FHIR R4
schema and structural errors are reported.

Unfixable issues (pipe in id, invalid references, schema errors) are written
to stderr.  The fixed output is still written so you can inspect and correct manually.
Exit code is 0 when all resources are fully fixed, 1 when any unfixable issues remain.

Usage:
    python tools/fix_fhir_bundle.py \\
        --input bundle.json --output fixed.json \\
        --meta-source https://example.org \\
        --owner my-org

    python tools/fix_fhir_bundle.py \\
        --input bundle.json --output fixed.json \\
        --meta-source https://example.org \\
        --owner my-org \\
        --access my-org \\
        --source-assigning-authority my-org

    python tools/fix_fhir_bundle.py \\
        --input bundle.json --output - \\
        --meta-source https://example.org \\
        --owner my-org
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

OWNER_SYSTEM = "https://www.icanbwell.com/owner"
ACCESS_SYSTEM = "https://www.icanbwell.com/access"
SOURCE_ASSIGNING_AUTHORITY_SYSTEM = "https://www.icanbwell.com/sourceAssigningAuthority"

# UUIDv5 namespace used by the server (OID namespace, from src/utils/uid.util.js)
_OID_NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
# FHIR relative reference: ResourceType/id
_RELATIVE_REF_RE = re.compile(r"^[A-Z][a-zA-Z]+/\S+$")

try:
    import fhirschemapy.R4B as _fhir_r4b
    from pydantic import ValidationError as _PydanticValidationError

    _FHIR_SCHEMA_AVAILABLE = True
except ImportError:
    _FHIR_SCHEMA_AVAILABLE = False


class FhirBundleFixer:
    """
    Fixes a FHIR Bundle, Parameters document, or single resource so it passes
    bwell FHIR server merge validation.

    Configure the fixer once via the constructor, then call ``fix()`` for each
    payload you want to process.  The instance is safe to reuse across calls.

    Example::

        fixer = FhirBundleFixer(meta_source="https://example.org", owner="my-org")
        fixed_payload, results = fixer.fix(payload)
        for label, changes, errors in results:
            ...
    """

    def __init__(
        self,
        *,
        meta_source: str | None = None,
        owner: str | None = None,
        access: str | None = None,
        source_assigning_authority: str | None = None,
    ) -> None:
        self.meta_source = meta_source
        self.owner = owner
        self.access = access
        self.source_assigning_authority = source_assigning_authority

    def fix(
        self,
        payload: dict[str, Any],
        *,
        patient_id: str | None = None,
    ) -> tuple[dict[str, Any], list[tuple[str, list[str], list[str]]]]:
        """
        Fix all resources in a Bundle, Parameters, or single resource.

        Optionally rewrites the Patient resource id and all Patient/<old-id>
        cross-references when *patient_id* is supplied.

        Returns ``(fixed_payload, results)`` where *results* is a list of
        ``(label, changes, errors)`` — one entry per top-level resource processed.
        Changes and errors are human-readable strings describing what was done or
        what could not be auto-fixed.
        """
        if patient_id is not None:
            self.apply_patient_id(payload, patient_id)

        return self._fix_payload(payload)

    # ── static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def is_uuid(value: str) -> bool:
        return bool(_UUID_RE.match(value))

    @staticmethod
    def deterministic_uuid(resource_id: str, source_assigning_authority: str) -> str:
        """Reproduce the server's UUIDv5 for a non-UUID id."""
        return str(uuid.uuid5(_OID_NAMESPACE, f"{resource_id}|{source_assigning_authority}"))

    @staticmethod
    def is_valid_reference(ref: str) -> bool:
        if ref.startswith("#"):
            return len(ref) > 1
        if ref.startswith("http://") or ref.startswith("https://"):
            return True
        if ref.startswith("urn:uuid:") or ref.startswith("urn:oid:"):
            return True
        return bool(_RELATIVE_REF_RE.match(ref))

    @staticmethod
    def _build_urn_ref_map(payload: dict[str, Any]) -> dict[str, str]:
        """
        Build a map from urn:uuid: fullUrls to ResourceType/id references.

        Called after all resources have been fixed so that generated ids are
        already in place.
        """
        ref_map: dict[str, str] = {}
        for entry in payload.get("entry", []):
            full_url = entry.get("fullUrl", "")
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")
            resource_id = resource.get("id")
            if full_url.startswith("urn:uuid:") and resource_type and resource_id:
                ref_map[full_url] = f"{resource_type}/{resource_id}"
        return ref_map

    @staticmethod
    def _fix_references(obj: Any, ref_map: dict[str, str]) -> int:
        """
        Recursively walk a JSON object and replace urn:uuid: references using
        *ref_map*.  Returns the number of replacements made.
        """
        count = 0
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "reference" and isinstance(value, str) and value in ref_map:
                    obj[key] = ref_map[value]
                    count += 1
                else:
                    count += FhirBundleFixer._fix_references(value, ref_map)
        elif isinstance(obj, list):
            for item in obj:
                count += FhirBundleFixer._fix_references(item, ref_map)
        return count

    @staticmethod
    def _replace_patient_references(obj: Any, old_id: str, new_id: str) -> int:
        """
        Recursively replace all Patient/<old_id> references with Patient/<new_id>.

        Returns the number of replacements made.
        """
        count = 0
        if isinstance(obj, dict):
            if isinstance(obj.get("reference"), str):
                target = f"Patient/{old_id}"
                if obj["reference"] == target:
                    obj["reference"] = f"Patient/{new_id}"
                    count += 1
            for value in obj.values():
                count += FhirBundleFixer._replace_patient_references(value, old_id, new_id)
        elif isinstance(obj, list):
            for item in obj:
                count += FhirBundleFixer._replace_patient_references(item, old_id, new_id)
        return count

    @staticmethod
    def apply_patient_id(payload: dict[str, Any], new_patient_id: str) -> tuple[int, int]:
        """
        Find the Patient resource in the payload, set its id to new_patient_id, and
        replace all Patient/<old-id> references throughout the payload.

        Returns (references_replaced, patient_id_changed) — patient_id_changed is 1
        if the Patient resource's id was actually different from new_patient_id, else 0.
        """
        old_id: str | None = None

        def _find_patient(resources: list[dict[str, Any]]) -> str | None:
            for r in resources:
                if r.get("resourceType") == "Patient":
                    return str(r.get("id", "")) or None
            return None

        resource_type = payload.get("resourceType")
        if resource_type == "Bundle":
            resources = [e["resource"] for e in payload.get("entry", []) if "resource" in e]
            old_id = _find_patient(resources)
        elif resource_type == "Parameters":
            resources = [p["resource"] for p in payload.get("parameter", []) if "resource" in p]
            old_id = _find_patient(resources)
        elif resource_type == "Patient":
            old_id = str(payload.get("id", "")) or None
        else:
            old_id = None

        if old_id is None or old_id == new_patient_id:
            return 0, 0

        def _set_patient_id(obj: Any) -> None:
            if isinstance(obj, dict):
                if obj.get("resourceType") == "Patient":
                    obj["id"] = new_patient_id
                for value in obj.values():
                    _set_patient_id(value)
            elif isinstance(obj, list):
                for item in obj:
                    _set_patient_id(item)

        _set_patient_id(payload)
        refs_replaced = FhirBundleFixer._replace_patient_references(payload, old_id, new_patient_id)
        return refs_replaced, 1

    @staticmethod
    def _collect_invalid_references(obj: Any, path: str) -> list[str]:
        issues = []
        if isinstance(obj, dict):
            if "reference" in obj and isinstance(obj["reference"], str):
                ref = obj["reference"]
                if not FhirBundleFixer.is_valid_reference(ref):
                    issues.append(
                        f"invalid reference at {path}.reference: {ref!r} "
                        "(expected #contained, https://..., or ResourceType/id)"
                    )
            for key, value in obj.items():
                issues.extend(FhirBundleFixer._collect_invalid_references(value, f"{path}.{key}"))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                issues.extend(FhirBundleFixer._collect_invalid_references(item, f"{path}[{i}]"))
        return issues

    @staticmethod
    def _validate_fhir_schema(resource: dict[str, Any]) -> list[str]:
        """Validate against the FHIR R4 schema using fhirschemapy. Returns error strings."""
        if not _FHIR_SCHEMA_AVAILABLE:
            return []
        resource_type = resource.get("resourceType")
        if not resource_type:
            return []
        # Bundle validation requires the aidbox package (not installed); skip it —
        # Bundle structure is handled by _fix_payload, not by schema validation here.
        if resource_type in ("Bundle", "Parameters"):
            return []
        model_class = getattr(_fhir_r4b, resource_type, None)
        if model_class is None:
            return [f"unknown resourceType {resource_type!r} — not in FHIR R4 schema"]
        try:
            # Strip contained before validating — contained resources are fixed separately
            # and their presence triggers an aidbox-dependent resource_families lookup.
            resource_for_validation = {k: v for k, v in resource.items() if k != "contained"}
            model_class.model_validate(resource_for_validation)
            return []
        except _PydanticValidationError as exc:
            return [f"schema: {e['loc']} — {e['msg']}" for e in exc.errors()]

    # ── private instance methods ──────────────────────────────────────────────

    def _apply_meta_security(
        self,
        resource: dict[str, Any],
        label: str,
    ) -> tuple[list[str], list[str]]:
        """
        Apply meta.source and security tag fixes to *resource* in place.

        Returns ``(changes, errors)`` with messages prefixed by *label*.
        Called for every top-level resource including the Bundle container itself.
        """
        changes: list[str] = []
        errors: list[str] = []

        def note(msg: str) -> None:
            changes.append(f"{label}: {msg}")

        def fail(msg: str) -> None:
            errors.append(f"{label}: {msg}")

        if "meta" not in resource:
            resource["meta"] = {}

        if not resource["meta"].get("source"):
            if self.meta_source:
                resource["meta"]["source"] = self.meta_source
                note(f"set meta.source = {self.meta_source!r}")
            else:
                fail("missing meta.source — provide meta_source")

        if "security" not in resource["meta"]:
            resource["meta"]["security"] = []

        before = len(resource["meta"]["security"])
        resource["meta"]["security"] = [t for t in resource["meta"]["security"] if t.get("system") and t.get("code")]
        removed = before - len(resource["meta"]["security"])
        if removed:
            note(f"removed {removed} security tag(s) with null/empty system or code")

        def tags_for(system: str) -> list[dict[str, Any]]:
            return [t for t in resource["meta"]["security"] if t.get("system") == system]

        def add_tag(system: str, code: str, label_: str) -> None:
            resource["meta"]["security"].append({"system": system, "code": code})
            note(f"added {label_} tag (code={code!r})")

        owner_tags = tags_for(OWNER_SYSTEM)
        if len(owner_tags) == 0:
            if self.owner:
                add_tag(OWNER_SYSTEM, self.owner, "owner")
            else:
                fail("missing owner security tag — provide owner")
        elif len(owner_tags) > 1:
            kept = owner_tags[0]
            resource["meta"]["security"] = [t for t in resource["meta"]["security"] if t.get("system") != OWNER_SYSTEM]
            resource["meta"]["security"].append(kept)
            note(f"removed {len(owner_tags) - 1} duplicate owner tag(s), kept code={kept['code']!r}")

        access_code = self.access or self.owner
        if access_code and not tags_for(ACCESS_SYSTEM):
            add_tag(ACCESS_SYSTEM, access_code, "access")

        if self.source_assigning_authority and not tags_for(SOURCE_ASSIGNING_AUTHORITY_SYSTEM):
            add_tag(SOURCE_ASSIGNING_AUTHORITY_SYSTEM, self.source_assigning_authority, "sourceAssigningAuthority")

        return changes, errors

    def _fix_resource(
        self,
        resource: dict[str, Any],
        *,
        is_contained: bool = False,
        path: str = "",
    ) -> tuple[dict[str, Any], list[str], list[str]]:
        """
        Fix a single FHIR resource in place and recurse into contained[] and
        nested Bundle entries.

        ``is_contained=True`` skips meta.source and security tag requirements,
        which do not apply to contained (inline) resources since they are
        validated as part of their parent.

        Returns ``(fixed_resource, changes, errors)``.
        """
        changes: list[str] = []
        errors: list[str] = []
        label = f"{resource.get('resourceType', '?')}/{resource.get('id', '?')}"
        prefix = f"{path}{label}: " if path else ""

        def note(msg: str) -> None:
            changes.append(f"{prefix}{msg}")

        def fail(msg: str) -> None:
            errors.append(f"{prefix}{msg}")

        if not resource.get("resourceType"):
            fail("missing resourceType — fix manually")

        # ── meta.source and security tags (top-level resources only) ─────────
        if not is_contained:
            meta_changes, meta_errors = self._apply_meta_security(resource, f"{path}{label}")
            changes.extend(meta_changes)
            errors.extend(meta_errors)

        # ── id (applies to all resources including contained) ─────────────────
        if not resource.get("id"):
            new_id = str(uuid.uuid4())
            resource["id"] = new_id
            note(f"generated random id = {new_id!r}")

        resource_id = str(resource.get("id", ""))

        if "|" in resource_id:
            fail(
                f"id contains a pipe character '|': {resource_id!r} — "
                "remove the pipe and set source_assigning_authority to the portion after it"
            )
        elif not is_contained and not self.is_uuid(resource_id):
            security = resource.get("meta", {}).get("security", [])
            has_owner = any(t.get("system") == OWNER_SYSTEM for t in security)
            has_saa = any(t.get("system") == SOURCE_ASSIGNING_AUTHORITY_SYSTEM for t in security)
            if not has_owner and not has_saa:
                saa = self.source_assigning_authority or self.owner
                if saa:
                    resource["meta"]["security"].append({"system": SOURCE_ASSIGNING_AUTHORITY_SYSTEM, "code": saa})
                    note(f"added sourceAssigningAuthority tag (code={saa!r}) — required for non-UUID id")
                else:
                    fail(
                        "non-UUID id requires an owner or sourceAssigningAuthority security tag — "
                        "provide owner or source_assigning_authority"
                    )

        # ── references ────────────────────────────────────────────────────────
        # Exclude subtrees that are walked recursively to avoid duplicate reports.
        skip_keys = set()
        if resource.get("resourceType") == "Bundle":
            skip_keys.add("entry")
        if isinstance(resource.get("contained"), list):
            skip_keys.add("contained")
        resource_for_refs = {k: v for k, v in resource.items() if k not in skip_keys}
        for issue in self._collect_invalid_references(resource_for_refs, label):
            fail(issue)

        # ── FHIR schema validation ────────────────────────────────────────────
        for issue in self._validate_fhir_schema(resource):
            fail(issue)

        # ── contained resources (recurse, skip meta/security) ─────────────────
        if isinstance(resource.get("contained"), list):
            fixed_contained = []
            for cr in resource["contained"]:
                fixed_cr, cr_changes, cr_errors = self._fix_resource(cr, is_contained=True, path=f"{prefix}contained/")
                fixed_contained.append(fixed_cr)
                changes.extend(cr_changes)
                errors.extend(cr_errors)
            resource["contained"] = fixed_contained

        # ── nested Bundle entries (recurse with full fixes) ────────────────────
        if resource.get("resourceType") == "Bundle" and isinstance(resource.get("entry"), list):
            for i, entry in enumerate(resource["entry"]):
                if "resource" in entry:
                    fixed_r, r_changes, r_errors = self._fix_resource(
                        entry["resource"], is_contained=False, path=f"{prefix}entry[{i}]/"
                    )
                    entry["resource"] = fixed_r
                    changes.extend(r_changes)
                    errors.extend(r_errors)

        return resource, changes, errors

    def _fix_payload(
        self,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], list[tuple[str, list[str], list[str]]]]:
        resource_type = payload.get("resourceType")
        results: list[tuple[str, list[str], list[str]]] = []

        if resource_type == "Bundle":
            bundle_label = f"Bundle/{payload.get('id', '<no id>')}"
            bundle_changes, bundle_errors = self._apply_meta_security(payload, bundle_label)
            results.append((bundle_label, bundle_changes, bundle_errors))

            for entry in payload.get("entry", []):
                if "resource" in entry:
                    r = entry["resource"]
                    label = f"{r.get('resourceType', 'Unknown')}/{r.get('id', '<no id>')}"
                    fixed, changes, errors = self._fix_resource(r)
                    entry["resource"] = fixed
                    results.append((label, changes, errors))

            ref_map = self._build_urn_ref_map(payload)
            if ref_map:
                replaced = self._fix_references(payload, ref_map)
                if replaced:
                    bundle_label = results[0][0]
                    results[0][1].append(
                        f"{bundle_label}: rewrote {replaced} urn:uuid: reference(s) to ResourceType/id"
                    )

            return payload, results

        if resource_type == "Parameters":
            for param in payload.get("parameter", []):
                if "resource" in param:
                    r = param["resource"]
                    label = f"{r.get('resourceType', 'Unknown')}/{r.get('id', '<no id>')}"
                    fixed, changes, errors = self._fix_resource(r)
                    param["resource"] = fixed
                    results.append((label, changes, errors))
            return payload, results

        label = f"{payload.get('resourceType', 'Unknown')}/{payload.get('id', '<no id>')}"
        fixed, changes, errors = self._fix_resource(payload)
        results.append((label, changes, errors))
        return fixed, results


# ── CLI ───────────────────────────────────────────────────────────────────────


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        metavar="PATH",
        required=True,
        help="Path to a FHIR Bundle, Parameters, or single resource JSON file.",
    )
    parser.add_argument(
        "--output",
        "-O",
        metavar="PATH",
        required=True,
        help="Path to write the fixed JSON file. Use - for stdout.",
    )
    parser.add_argument(
        "--meta-source",
        "-s",
        metavar="URL",
        help="Value to set on meta.source for each resource that is missing it.",
    )
    parser.add_argument(
        "--owner",
        "-o",
        metavar="CODE",
        help=(
            "Code for the owner security tag "
            f"(system: {OWNER_SYSTEM}). "
            "Also used as the default for --access and --source-assigning-authority."
        ),
    )
    parser.add_argument(
        "--access",
        "-c",
        metavar="CODE",
        help=(f"Code for the access security tag (system: {ACCESS_SYSTEM}). Defaults to --owner if not specified."),
    )
    parser.add_argument(
        "--source-assigning-authority",
        "-a",
        metavar="CODE",
        help=(
            f"Code for the sourceAssigningAuthority tag (system: {SOURCE_ASSIGNING_AUTHORITY_SYSTEM}). "
            "Added to every top-level resource. For non-UUID ids, also satisfies the id-format "
            "requirement when --owner is not provided. Defaults to --owner when needed."
        ),
    )
    parser.add_argument(
        "--patient-id",
        "-p",
        metavar="ID",
        help=(
            "New patient ID to use. The Patient resource's id is set to this value "
            "and all Patient/<old-id> references throughout the payload are updated to "
            "Patient/<new-id>. Has no effect if no Patient resource is found."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes and errors without writing any output.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"ERROR: file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON — {exc}", file=sys.stderr)
        return 1

    fixer = FhirBundleFixer(
        meta_source=args.meta_source,
        owner=args.owner,
        access=args.access,
        source_assigning_authority=args.source_assigning_authority,
    )

    patient_id: str | None = args.patient_id
    if patient_id is not None:
        refs_replaced, id_changed = FhirBundleFixer.apply_patient_id(payload, patient_id)
        if id_changed:
            print(
                f"Patient id set to {patient_id!r}; {refs_replaced} Patient reference(s) updated.",
                file=sys.stderr,
            )
        else:
            print(
                f"--patient-id specified but no Patient resource found or id already matches; "
                f"{refs_replaced} Patient reference(s) updated.",
                file=sys.stderr,
            )

    fixed_payload, results = fixer.fix(payload)

    if not results:
        print("ERROR: no resources found in input", file=sys.stderr)
        return 1

    total_changes = 0
    total_errors = 0

    for i, (label, changes, errors) in enumerate(results, start=1):
        if changes or errors:
            print(f"\n[{i}] {label}", file=sys.stderr)
        for change in changes:
            print(f"  + {change}", file=sys.stderr)
            total_changes += 1
        for error in errors:
            print(f"  ! {error}", file=sys.stderr)
            total_errors += 1

    schema_note = " (fhirschemapy schema validation included)" if _FHIR_SCHEMA_AVAILABLE else ""
    print(
        f"\nSummary{schema_note}: {len(results)} top-level resource(s), "
        f"{total_changes} fix(es) applied, "
        f"{total_errors} unfixable issue(s).",
        file=sys.stderr,
    )

    if args.dry_run:
        print("Dry run — no output written.", file=sys.stderr)
        return 1 if total_errors else 0

    output_json = json.dumps(fixed_payload, indent=2)
    if args.output == "-":
        print(output_json)
    else:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Wrote fixed output to {args.output}", file=sys.stderr)

    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
