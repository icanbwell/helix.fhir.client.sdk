import dataclasses
from typing import Optional


@dataclasses.dataclass
class FhirScopeParserResult:
    """
    This class stores the result from parsing a scope per:
    https://build.fhir.org/ig/HL7/smart-app-launch/scopes-and-launch-context.html

    """

    resource_type: Optional[str] = None
    operation: Optional[str] = None
    interaction: Optional[str] = None
    scope: Optional[str] = None
