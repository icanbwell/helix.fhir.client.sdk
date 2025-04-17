from datetime import datetime

from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class LastUpdatedFilter(BaseFilter):
    def __init__(self, less_than: datetime | None, greater_than: datetime | None) -> None:
        """
        Returns resources between the date ranges


        :param less_than:
        :param greater_than:
        """
        assert less_than is None or isinstance(less_than, datetime)
        self.less_than: datetime | None = less_than
        assert greater_than is None or isinstance(greater_than, datetime)
        self.greater_than: datetime | None = greater_than

    def __str__(self) -> str:
        filters: list[str] = []
        if self.less_than is not None:
            filters.append(f"_lastUpdated=lt{self.less_than.strftime('%Y-%m-%d')}")
        if self.greater_than is not None:
            filters.append(f"_lastUpdated=gt{self.greater_than.strftime('%Y-%m-%d')}")
        return "&".join(filters)
