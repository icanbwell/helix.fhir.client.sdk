from typing import List, Any, Dict, Optional


class GraphDefinitionTarget:
    def __init__(
        self,
        *,
        type_: str,
        params: Optional[str] = None,
        link: Optional[List["GraphDefinitionLink"]] = None
    ):
        """
        Create a target for a link
        :param type_: Type of child resource
        :param params: Used for a reverse link where the child resource has a property that is a reference
                        back to the parent
        :param link: Nested for additional links to children of this child resource
        """
        self.type_: str = type_
        self.params: Optional[str] = params
        self.link: Optional[List["GraphDefinitionLink"]] = link

    def to_dict(self) -> Dict[str, Any]:
        my_dict: Dict[str, Any] = {"type": self.type_}
        if self.params:
            my_dict["params"] = self.params
        if self.link:
            my_dict["link"] = [link.to_dict() for link in self.link]
        return my_dict


class GraphDefinitionLink:
    def __init__(
        self, *, path: Optional[str] = None, target: List[GraphDefinitionTarget]
    ):
        """
        Create a link to another resource

        :param path: Optional path for forward links i.e., the parent resource has a property that is a reference
                        to this related resource
        :param target: list of targeted resources.
        """
        self.path: Optional[str] = path
        self.target: List[GraphDefinitionTarget] = target

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns this object as a dictionary
        """
        my_dict: Dict[str, Any] = {
            "target": [target.to_dict() for target in self.target]
        }
        if self.path:
            my_dict["path"] = self.path
        return my_dict


class GraphDefinition:
    def __init__(
        self, *, id_: str, name: str, start: str, link: List[GraphDefinitionLink]
    ):
        """
        Creates a GraphDefinition object to use in a $graph call

        :param id_: id for this GraphDefinition resource
        :param start: Fhir Resource to start from
        :param link: list of links
        """
        self.resourceType: str = "GraphDefinition"
        self.id_: str = id_
        self.name: str = name
        self.start: str = start
        self.link: List[GraphDefinitionLink] = link

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns this object as a dictionary
        """
        my_dict: Dict[str, Any] = {
            "resourceType": self.resourceType,
            "id": self.id_,
            "name": self.name,
            "status": "active",
            "start": self.start,
            "link": [link.to_dict() for link in self.link],
        }
        return my_dict
