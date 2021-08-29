from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class SecurityAccessFilter(BaseFilter):
    def __init__(self, value: str) -> None:
        """
        Restrict results to only records that have an access tag for this client_id


        :param value: client id
        """
        assert value
        self.value: str = value

    def __str__(self) -> str:
        return f"_security=https://www.icanbwell.com/access|{self.value}"
