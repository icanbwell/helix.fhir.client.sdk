import dataclasses


@dataclasses.dataclass(slots=True)
class FhirScopeParserResult:
    """
    This class stores the result from parsing a scope per:
    https://build.fhir.org/ig/HL7/smart-app-launch/scopes-and-launch-context.html

    """

    resource_type: str | None = None
    operation: str | None = None
    interaction: str | None = None
    scope: str | None = None
