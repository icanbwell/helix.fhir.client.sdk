from typing import List

from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser
from helix_fhir_client_sdk.utilities.fhir_scope_parser_result import (
    FhirScopeParserResult,
)


def test_fhir_scope_parser_can_parse_scopes() -> None:
    scope_parser_result: List[FhirScopeParserResult] = FhirScopeParser.parse_scopes(
        scopes="""
patient/AllergyIntolerance.read patient/Binary.read patient/CarePlan.read patient/CareTeam.read patient/Condition.read patient/Device.read patient/DiagnosticReport.read patient/DocumentReference.read patient/Encounter.read patient/Goal.read patient/Immunization.read patient/Location.read patient/Medication.read patient/MedicationRequest.read patient/Observation.read patient/Organization.read patient/Patient.read patient/Practitioner.read patient/PractitionerRole.read patient/Procedure.read patient/Provenance.read patient/RelatedPerson.Read launch/patient        
        """
    )
    assert scope_parser_result == [
        FhirScopeParserResult(
            resource_type="patient",
            operation="AllergyIntolerance",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient", operation="Binary", interaction="read", scope=None
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="CarePlan",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="CareTeam",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Condition",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient", operation="Device", interaction="read", scope=None
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="DiagnosticReport",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="DocumentReference",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Encounter",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient", operation="Goal", interaction="read", scope=None
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Immunization",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Location",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Medication",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="MedicationRequest",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Observation",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Organization",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient", operation="Patient", interaction="read", scope=None
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Practitioner",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="PractitionerRole",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Procedure",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="Provenance",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="patient",
            operation="RelatedPerson",
            interaction="read",
            scope=None,
        ),
        FhirScopeParserResult(
            resource_type="launch", operation=None, interaction="patient", scope=None
        ),
    ]
