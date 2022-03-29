from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class PropertyMissingFilter(BaseFilter):
    def __init__(self, property_: str, missing: bool) -> None:
        """
        Filter to find records where the specified property is missing or not missing

        :param property_: name of property
        :param missing: whether we're checking if it is missing or whether we're checking if it is not missing
        """
        assert property_
        assert missing is not None
        self.property_: str = property_
        self.missing: bool = missing

    def __str__(self) -> str:
        return f"{self.property_}:missing={'true' if self.missing else 'false'}"
