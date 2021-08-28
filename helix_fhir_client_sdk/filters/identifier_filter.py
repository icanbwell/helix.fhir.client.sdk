from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class IdentifierFilter(BaseFilter):
    def __init__(self, system: str, value: str) -> None:
        self.system: str = system
        self.value: str = value

    def __str__(self) -> str:
        return f"identifier={self.system}|{self.value}"
