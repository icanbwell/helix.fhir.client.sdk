import dataclasses
from typing import Dict, Any, List


@dataclasses.dataclass(slots=True)
class BundleExpanderResult:
    resources: List[Dict[str, Any]]
    total_count: int


class BundleExpander:
    @staticmethod
    async def expand_bundle_async(
        *,
        bundle: Dict[str, Any],
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
        resources_list: List[Dict[str, Any]] = []
        if "entry" in bundle:
            entries: List[Dict[str, Any]] = bundle["entry"]
            entry: Dict[str, Any]
            for entry in entries:
                if "resource" in entry:
                    resources_list.append(entry["resource"])

        return BundleExpanderResult(resources=resources_list, total_count=total_count)
