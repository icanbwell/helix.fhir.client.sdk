import dataclasses
from typing import Any, cast


@dataclasses.dataclass(slots=True)
class ResourceSeparatorResult:
    """
    ResourceSeparatorResult class for encapsulating the response from FHIR server when separating resources
    """

    resources_dicts: list[dict[str, str | None | list[dict[str, Any]]]]
    total_count: int


class ResourceSeparator:
    """
    ResourceSeparator class for separating resources from contained resources
    """

    @staticmethod
    async def separate_contained_resources_async(
        *,
        resources: list[dict[str, Any]],
        access_token: str | None,
        url: str | None,
        extra_context_to_return: dict[str, Any] | None,
    ) -> ResourceSeparatorResult:
        """
        Separate contained resources without copying or mutating input resources.
        """
        resources_dicts: list[dict[str, str | None | list[dict[str, Any]]]] = []
        total_resource_count: int = 0

        for parent_resource in resources:
            resource_type_value = parent_resource.get("resourceType")
            if not resource_type_value:
                continue

            resource_type_key = str(resource_type_value).lower()
            resource_map: dict[str, str | None | list[dict[str, Any]]] = {}

            # Add parent resource
            parent_list = cast(list[dict[str, Any]], resource_map.setdefault(resource_type_key, []))
            parent_list.append(parent_resource)
            total_resource_count += 1

            # Add contained resources (if present) without mutating parent
            contained_list = parent_resource.get("contained")
            if isinstance(contained_list, list) and contained_list:
                total_resource_count += len(contained_list)
                for contained_resource in contained_list:
                    contained_type_value = contained_resource.get("resourceType")
                    if not contained_type_value:
                        continue
                    contained_type_key = str(contained_type_value).lower()
                    contained_list_out = cast(list[dict[str, Any]], resource_map.setdefault(contained_type_key, []))
                    contained_list_out.append(contained_resource)

            # Context
            resource_map["token"] = access_token
            resource_map["url"] = url
            if extra_context_to_return:
                resource_map.update(extra_context_to_return)

            resources_dicts.append(resource_map)

        return ResourceSeparatorResult(resources_dicts=resources_dicts, total_count=total_resource_count)
