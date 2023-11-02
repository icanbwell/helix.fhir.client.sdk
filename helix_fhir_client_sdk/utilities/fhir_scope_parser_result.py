import dataclasses
from typing import Optional


@dataclasses.dataclass
class FhirScopeParserResult:
    resource_type: Optional[str] = None
    operation: Optional[str] = None
    interaction: Optional[str] = None
    scope: Optional[str] = None
