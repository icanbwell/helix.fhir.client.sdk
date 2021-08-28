from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class SecurityOwnerFilter(BaseFilter):
    def __init__(self, value: str) -> None:
        self.value: str = value

    def __str__(self) -> str:
        return f"_security=https://www.icanbwell.com/owner|{self.value}"
