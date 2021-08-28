from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class IdentifierFilter(BaseFilter):
    def __init__(self, system: str, value: str) -> None:
        """
        Restrict results to only records that have an identifier with this system and value
        Example: system= http://hl7.org/fhir/sid/us-npi, value= 1487831681


        :param system: system of identifier.  Note that this is the assigning system NOT the coding system
        :param value: value of identifier.  This matches the value of the identifier NOT the code
        """
        assert system
        assert value
        self.system: str = system
        self.value: str = value

    def __str__(self) -> str:
        return f"identifier={self.system}|{self.value}"
