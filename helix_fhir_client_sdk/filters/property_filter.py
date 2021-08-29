from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class PropertyFilter(BaseFilter):
    def __init__(self, property_: str, value: str) -> None:
        """
        Filters the data where the specified property equals the specified value


        :param property_: property name
        :param value: value to match to
        """
        assert property_
        assert value
        self.property_: str = property_
        self.value: str = value

    def __str__(self) -> str:
        return f"{self.property_}={self.value}"
