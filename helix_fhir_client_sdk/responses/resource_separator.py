import dataclasses
from copy import deepcopy
from typing import List, Dict, Any, Optional, cast


@dataclasses.dataclass(slots=True)
class ResourceSeparatorResult:
    """
    ResourceSeparatorResult class for encapsulating the response from FHIR server when separating resources
    """

    resources_dicts: List[Dict[str, Optional[str] | List[Dict[str, Any]]]]
    total_count: int


class ResourceSeparator:
    """
    ResourceSeparator class for separating resources from contained resources
    """

    @staticmethod
    async def separate_contained_resources_async(
        *,
        resources: List[Dict[str, Any]],
        access_token: Optional[str],
        url: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
    ) -> ResourceSeparatorResult:
        """
        Given a list of resources, return a list of resources with the contained resources separated out.

        :param resources: The resources list.
        :param access_token: The access token.
        :param url: The URL.
        :param extra_context_to_return: The extra context to return.

        :return: None
        """
        resources_dicts: List[Dict[str, Optional[str] | List[Dict[str, Any]]]] = []
        resource_count: int = 0
        resource: Dict[str, Any]
        for resource in resources:
            # make a copy so we are not changing the original resource
            cloned_resource: Dict[str, Any] = deepcopy(resource)
            # This dict will hold the separated resources where the key is resourceType
            # have to split these here otherwise when Spark loads them
            # it can't handle that items in the entry array can have different schemas
            resources_dict: Dict[str, Optional[str] | List[Dict[str, Any]]] = {}
            # add the parent resource to the resources_dict
            resource_type = str(cloned_resource["resourceType"]).lower()
            if resource_type not in resources_dict:
                resources_dict[resource_type] = []
            if isinstance(resources_dict[resource_type], list):
                cast(List[Dict[str, Any]], resources_dict[resource_type]).append(
                    cloned_resource
                )
                resource_count += 1
            # now see if this resource has a contained array and if so, add those to the resources_dict
            if "contained" in cloned_resource:
                contained_resources = cloned_resource.pop("contained")
                for contained_resource in contained_resources:
                    resource_type = str(contained_resource["resourceType"]).lower()
                    if resource_type not in resources_dict:
                        resources_dict[resource_type] = []
                    if isinstance(resources_dict[resource_type], list):
                        cast(
                            List[Dict[str, Any]], resources_dict[resource_type]
                        ).append(contained_resource)
                        resource_count += 1
            resources_dict["token"] = access_token
            resources_dict["url"] = url
            if extra_context_to_return:
                resources_dict.update(extra_context_to_return)
            resources_dicts.append(resources_dict)

        return ResourceSeparatorResult(
            resources_dicts=resources_dicts, total_count=resource_count
        )
