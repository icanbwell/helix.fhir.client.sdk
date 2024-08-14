from typing import List, Dict, Any, Optional, cast


class ResourceSeparator:
    @staticmethod
    async def separate_contained_resources_async(
        *,
        resources: List[Dict[str, Any]],
        access_token: Optional[str],
        url: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
    ) -> Dict[str, Optional[str] | List[Any]]:
        """
        Given a list of resources, return a list of resources with the contained resources separated out.

        :param resources: The resources list.
        :param access_token: The access token.
        :param url: The URL.
        :param extra_context_to_return: The extra context to return.

        :return: None
        """

        # This dict will hold the separated resources where the key is resourceType
        resources_dict: Dict[str, Optional[str] | List[Dict[str, Any]]] = {}

        # have to split these here otherwise when Spark loads them
        # it can't handle that items in the entry array can have different schemas
        resource: Dict[str, Any]
        for resource in resources:
            if "contained" in resource:
                contained_resources = resource.pop("contained")
                for contained_resource in contained_resources:
                    resource_type = str(contained_resource["resourceType"]).lower()
                    if resource_type not in resources_dict:
                        resources_dict[resource_type] = []
                    if isinstance(resources_dict[resource_type], list):
                        cast(
                            List[Dict[str, Any]], resources_dict[resource_type]
                        ).append(contained_resource)

        resources_dict["token"] = access_token
        resources_dict["url"] = url
        if extra_context_to_return:
            resources_dict.update(extra_context_to_return)

        return resources_dict
