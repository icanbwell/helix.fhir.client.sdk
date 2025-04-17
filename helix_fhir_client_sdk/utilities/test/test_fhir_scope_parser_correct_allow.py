from pytest import mark

from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser


@mark.parametrize(
    argnames="scopes,expected",
    argvalues=[
        (
            [
                (
                    "patient/AllergyIntolerance.read patient/Binary.read patient/CarePlan.read patient/CareTeam.read "
                    "patient/Condition.read patient/Device.read patient/DiagnosticReport.read "
                    "patient/DocumentReference.read patient/Encounter.read patient/Goal.read patient/Immunization.read "
                    "patient/Location.read patient/Medication.read patient/MedicationRequest.read "
                    "patient/Observation.read patient/Organization.read patient/Patient.read patient/Practitioner.read "
                    "patient/PractitionerRole.read patient/Procedure.read patient/Provenance.read "
                    "patient/RelatedPerson.read launch/patient"
                )
            ],
            [True, True, False, False],
        ),
        (
            [
                (
                    "user/AllergyIntolerance.read user/Binary.read user/CarePlan.read user/CareTeam.read "
                    "user/Condition.read user/Device.read user/DiagnosticReport.read user/DocumentReference.read "
                    "user/Encounter.read user/Goal.read user/Immunization.read user/Location.read user/Medication.read "
                    "user/MedicationDispense.read user/Observation.read user/Organization.read user/Patient.read "
                    "user/Practitioner.read user/PractitionerRole.read user/Procedure.read user/Provenance.read "
                    "user/RelatedPerson.read"
                )
            ],
            [True, True, True, False],
        ),
        (
            [
                (
                    "system/AllergyIntolerance.read system/Binary.read system/CarePlan.read system/CareTeam.read "
                    "system/Device.read system/DiagnosticReport.read system/DocumentReference.read "
                    "system/Encounter.read system/Goal.read system/Immunization.read system/Location.read "
                    "system/MedicationRequest.read system/Observation.read system/Organization.read "
                    "system/Patient.read system/Medication.read system/Practitioner.read system/PractitionerRole.read "
                    "system/Procedure.read system/Provenance.read system/RelatedPerson.read system/Patient.write"
                )
            ],
            [True, False, False, True],
        ),
        ([], [True, True, True, True]),
    ],
    ids=["Patient Scopes", "User Scopes", "System Scopes", "Non-SMART on FHIR Scopes"],
)
def test_fhir_scope_parser_correct_allow(scopes: list[str], expected: list[bool]) -> None:
    scope_parser: FhirScopeParser = FhirScopeParser(scopes)
    assert scope_parser.scope_allows(resource_type="Patient", interaction="read") is expected[0]
    assert scope_parser.scope_allows(resource_type="Condition", interaction="read") is expected[1]
    assert scope_parser.scope_allows(resource_type="MedicationDispense", interaction="read") is expected[2]
    assert scope_parser.scope_allows(resource_type="Patient", interaction="write") is expected[3]
