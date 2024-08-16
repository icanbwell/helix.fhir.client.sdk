from helix_fhir_client_sdk.utilities.fhir_scope_parser import FhirScopeParser
from helix_fhir_client_sdk.utilities.fhir_scope_parser_result import (
    FhirScopeParserResult,
)


def test_parse_scopes_empty() -> None:
    parser = FhirScopeParser(scopes=[])
    assert parser.parsed_scopes is None


def test_parse_scopes_none() -> None:
    parser = FhirScopeParser(scopes=None)
    assert parser.parsed_scopes is None


def test_parse_scopes_valid() -> None:
    scopes = ["patient/*.read", "user/*.write", "launch/patient"]
    parser = FhirScopeParser(scopes=scopes)
    expected = [
        FhirScopeParserResult(
            resource_type="patient", operation="*", interaction="read"
        ),
        FhirScopeParserResult(resource_type="user", operation="*", interaction="write"),
        FhirScopeParserResult(resource_type="launch", interaction="patient"),
    ]
    assert parser.parsed_scopes == expected


def test_parse_scopes_invalid() -> None:
    scopes = ["invalid_scope"]
    parser = FhirScopeParser(scopes=scopes)
    expected = [FhirScopeParserResult(scope="invalid_scope")]
    assert parser.parsed_scopes == expected


def test_scope_allows_no_scopes() -> None:
    parser = FhirScopeParser(scopes=None)
    assert parser.scope_allows("AnyResource")


def test_scope_allows_specific_scope() -> None:
    scopes = ["patient/*.read"]
    parser = FhirScopeParser(scopes=scopes)
    assert parser.scope_allows("patient", "read")
    assert not parser.scope_allows("patient", "write")


def test_scope_allows_wildcard_scope() -> None:
    scopes = ["patient/*.*"]
    parser = FhirScopeParser(scopes=scopes)
    assert parser.scope_allows("patient", "read")
    assert parser.scope_allows("patient", "write")


def test_scope_allows_always_allowed_resources() -> None:
    scopes = ["user/*.read"]
    parser = FhirScopeParser(scopes=scopes)
    assert parser.scope_allows("OperationOutcome")
    assert parser.scope_allows("Bundle")


def test_scope_allows_no_patient_user_system_scopes() -> None:
    scopes = ["launch/*.read"]
    parser = FhirScopeParser(scopes=scopes)
    assert parser.scope_allows("AnyResource")
