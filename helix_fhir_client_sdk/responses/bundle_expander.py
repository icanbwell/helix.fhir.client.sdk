import dataclasses
from typing import Any


@dataclasses.dataclass(slots=True)
class BundleExpanderResult:
    resources: list[dict[str, Any]]
    total_count: int


class BundleExpander:
    @staticmethod
    async def expand_bundle_async(
        *,
        bundle: dict[str, Any],
        total_count: int,
    ) -> BundleExpanderResult:
        """
        This method is responsible for expanding the FHIR bundle.

        :param bundle: The bundle.
        :param total_count: The total count.

        :return: A tuple of the resources in JSON format and the total count.
        """
        if "total" in bundle:
            total_count = int(bundle["total"])
        resources_list: list[dict[str, Any]] = []
        if "entry" in bundle:
            entries: list[dict[str, Any]] = bundle["entry"]
            entry: dict[str, Any]
            for entry in entries:
                if "resource" in entry:
                    resources_list.append(entry["resource"])

        return BundleExpanderResult(resources=resources_list, total_count=total_count)
