from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class SourceFilter(BaseFilter):
    def __init__(self, value: str) -> None:
        """
        Restrict results to records with this source

        :param value: source url
        """
        assert value
        self.value: str = value

    def __str__(self) -> str:
        return f"source={self.value}"
