import json
from logging import Logger
from os import environ
from typing import Any

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.fixers.fix_fhir_bundle import FhirBundleFixer
from helix_fhir_client_sdk.responses.fhir_merge_response import FhirMergeResponse
from helix_fhir_client_sdk.utilities.fhir_server_helpers import FhirServerHelpers
from tests.logger_for_test import LoggerForTest


async def test_fhir_bundle_fixer_fixes_and_merges_async() -> None:
    """
    Verifies that FhirBundleFixer corrects a bundle that has common merge-blocking
    issues and that the fixed resources are accepted by the bwell FHIR server.

    Issues introduced deliberately:
    - meta is absent entirely on both resources
    - one security tag has a null system (should be stripped)
    - Patient has a duplicate owner tag (should be de-duplicated)
    - Observation has no id (should have one generated)
    """
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Patient")
    await FhirServerHelpers.clean_fhir_server_async(resource_type="Observation")

    broken_bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "fixer-test-patient-1",
                    # no meta → fixer must add meta.source and security tags
                    # duplicate owner tag → fixer must de-duplicate
                    "meta": {
                        "security": [
                            # null-system tag → must be stripped
                            {"system": None, "code": "garbage"},
                            # duplicate owner tags → keep first, drop second
                            {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
                            {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
                        ]
                    },
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    # no id → fixer must generate a UUID
                    "status": "final",
                    "code": {"text": "test observation"},
                    "subject": {"reference": "Patient/fixer-test-patient-1"},
                    # no meta at all → fixer must add meta.source and all security tags
                }
            },
        ],
    }

    logger: Logger = LoggerForTest()

    fixer = FhirBundleFixer(
        meta_source="http://www.icanbwell.com",
        owner="bwell",
    )
    fixed_bundle, results = fixer.fix(broken_bundle)

    logger.info("=== FhirBundleFixer results ===")
    for label, changes, errors in results:
        logger.info(f"[{label}]")
        for c in changes:
            logger.info(f"  + {c}")
        for e in errors:
            logger.info(f"  ! {e}")

    # ── assert fixer reported the expected changes ────────────────────────────
    # results[0] = Bundle container, results[1] = Patient, results[2] = Observation
    assert len(results) == 3, f"Expected 3 results (Bundle + 2 resources), got {len(results)}: {results}"

    bundle_label, bundle_changes, bundle_errors = results[0]
    assert "Bundle" in bundle_label
    assert not bundle_errors, f"Unexpected Bundle errors: {bundle_errors}"
    bundle_change_text = " | ".join(bundle_changes)
    assert "meta.source" in bundle_change_text, f"Expected meta.source on Bundle in: {bundle_change_text}"
    assert "owner" in bundle_change_text, f"Expected owner tag on Bundle in: {bundle_change_text}"

    patient_label, patient_changes, patient_errors = results[1]
    assert "Patient" in patient_label
    assert not patient_errors, f"Unexpected Patient errors: {patient_errors}"

    patient_change_text = " | ".join(patient_changes)
    assert "meta.source" in patient_change_text, f"Expected meta.source fix in: {patient_change_text}"
    assert "null/empty" in patient_change_text, f"Expected null-tag strip in: {patient_change_text}"
    assert "duplicate owner" in patient_change_text, f"Expected owner de-dup in: {patient_change_text}"

    obs_label, obs_changes, obs_errors = results[2]
    assert "Observation" in obs_label
    assert not obs_errors, f"Unexpected Observation errors: {obs_errors}"

    obs_change_text = " | ".join(obs_changes)
    assert "generated random id" in obs_change_text, f"Expected id generation in: {obs_change_text}"
    assert "meta.source" in obs_change_text, f"Expected meta.source fix in: {obs_change_text}"
    assert "owner" in obs_change_text, f"Expected owner tag in: {obs_change_text}"
    assert "access" in obs_change_text, f"Expected access tag in: {obs_change_text}"

    # ── verify the fixed resource structure ───────────────────────────────────
    patient_resource = fixed_bundle["entry"][0]["resource"]
    assert patient_resource["meta"]["source"] == "http://www.icanbwell.com"

    owner_tags = [
        t for t in patient_resource["meta"]["security"] if t.get("system") == "https://www.icanbwell.com/owner"
    ]
    assert len(owner_tags) == 1, f"Expected exactly 1 owner tag: {owner_tags}"

    null_tags = [t for t in patient_resource["meta"]["security"] if not t.get("system")]
    assert not null_tags, f"Null-system tags were not stripped: {null_tags}"

    obs_resource = fixed_bundle["entry"][1]["resource"]
    assert obs_resource.get("id"), "Observation id was not generated"

    # ── merge each resource to the real FHIR server ───────────────────────────
    fhir_server_url: str = environ["FHIR_SERVER_URL"]
    auth_client_id = environ["FHIR_CLIENT_ID"]
    auth_client_secret = environ["FHIR_CLIENT_SECRET"]
    auth_well_known_url = environ["AUTH_CONFIGURATION_URI"]

    def make_client(resource_type: str) -> FhirClient:
        client = FhirClient()
        client = client.url(fhir_server_url).resource(resource_type)
        client = client.client_credentials(client_id=auth_client_id, client_secret=auth_client_secret)
        client = client.auth_wellknown_url(auth_well_known_url)
        return client

    logger.info("=== Merging Patient ===")
    patient_merge: FhirMergeResponse | None = await FhirMergeResponse.from_async_generator(
        make_client("Patient").merge_async(json_data_list=[json.dumps(patient_resource)])
    )
    assert patient_merge is not None
    logger.info(f"Patient merge status: {patient_merge.status}")
    logger.info(f"Patient merge response: {patient_merge.responses}")
    assert patient_merge.status == 200, patient_merge.responses
    assert len(patient_merge.responses) == 1, patient_merge.responses
    assert patient_merge.responses[0].get("created") is True, patient_merge.responses

    logger.info("=== Merging Observation ===")
    obs_merge: FhirMergeResponse | None = await FhirMergeResponse.from_async_generator(
        make_client("Observation").merge_async(json_data_list=[json.dumps(obs_resource)])
    )
    assert obs_merge is not None
    logger.info(f"Observation merge status: {obs_merge.status}")
    logger.info(f"Observation merge response: {obs_merge.responses}")
    assert obs_merge.status == 200, obs_merge.responses
    assert len(obs_merge.responses) == 1, obs_merge.responses
    assert obs_merge.responses[0].get("created") is True, obs_merge.responses
