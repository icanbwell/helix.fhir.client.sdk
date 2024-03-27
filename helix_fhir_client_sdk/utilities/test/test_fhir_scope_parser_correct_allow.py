from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser


def test_fhir_scope_parser_correct_patient_allow() -> None:
    scope_parser: FhirScopeParser = FhirScopeParser(
        scopes=[
            (
                "patient/AllergyIntolerance.read patient/Binary.read patient/CarePlan.read patient/CareTeam.read "
                "patient/Condition.read patient/Device.read patient/DiagnosticReport.read "
                "patient/DocumentReference.read patient/Encounter.read patient/Goal.read patient/Immunization.read "
                "patient/Location.read patient/Medication.read patient/MedicationRequest.read patient/Observation.read "
                "patient/Organization.read patient/Patient.read patient/Practitioner.read "
                "patient/PractitionerRole.read patient/Procedure.read patient/Provenance.read "
                "patient/RelatedPerson.read launch/patient"
            )
        ]
    )

    assert (
        scope_parser.scope_allows(resource_type="Patient", interaction="read") is True
    )

    assert (
        scope_parser.scope_allows(resource_type="Condition", interaction="read") is True
    )

    assert (
        scope_parser.scope_allows(
            resource_type="MedicationDispense", interaction="read"
        )
        is False
    )

    assert (
        scope_parser.scope_allows(resource_type="Patient", interaction="write") is False
    )


def test_fhir_scope_parser_correct_user_allow() -> None:
    user_scope_parser: FhirScopeParser = FhirScopeParser(
        scopes=[
            (
                "user/AllergyIntolerance.read user/Binary.read user/CarePlan.read user/CareTeam.read "
                "user/Condition.read user/Device.read user/DiagnosticReport.read user/DocumentReference.read "
                "user/Encounter.read user/Goal.read user/Immunization.read user/Location.read user/Medication.read "
                "user/MedicationRequest.read user/Observation.read user/Organization.read user/Patient.read "
                "user/Practitioner.read user/PractitionerRole.read user/Procedure.read user/Provenance.read "
                "user/RelatedPerson.read"
            )
        ]
    )

    assert (
        user_scope_parser.scope_allows(resource_type="Patient", interaction="read")
        is True
    )

    assert (
        user_scope_parser.scope_allows(resource_type="Condition", interaction="read")
        is True
    )

    assert (
        user_scope_parser.scope_allows(
            resource_type="MedicationDispense", interaction="read"
        )
        is False
    )

    assert (
        user_scope_parser.scope_allows(resource_type="Patient", interaction="write")
        is False
    )
