from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class IdentifierFilter(BaseFilter):
    def __init__(self, system: str, value: str) -> None:
        """
        Filter for finding records where there is an identifier with sytem and value


        :param system: system of identifier.  Note that this is the assigning system NOT the coding system
        :param value: value of identifier.  This matches the value of the identifier NOT the code
        """
        self.system: str = system
        self.value: str = value

    def __str__(self) -> str:
        return f"identifier={self.system}|{self.value}"
