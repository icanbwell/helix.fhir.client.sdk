from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class PropertyFilter(BaseFilter):
    def __init__(self, property_: str, value: str) -> None:
        self.property_: str = property_
        self.value: str = value

    def __str__(self) -> str:
        return f"{self.property_}={self.value}"
