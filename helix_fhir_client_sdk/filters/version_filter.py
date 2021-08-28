from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class VersionFilter(BaseFilter):
    def __init__(self, value: int) -> None:
        """
        Returns specific version of the resources


        :param value: which version to return
        """
        assert value
        self.value: int = value

    def __str__(self) -> str:
        return f"versionId={self.value}"
