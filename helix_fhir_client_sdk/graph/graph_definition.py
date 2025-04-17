from typing import Any


class GraphDefinitionTarget:
    __slots__ = ["type_", "params", "link"]

    def __init__(
        self,
        *,
        type_: str,
        params: str | None = None,
        link: list["GraphDefinitionLink"] | None = None,
    ) -> None:
        """
        Create a target for a link
        :param type_: Type of child resource
        :param params: Used for a reverse link where the child resource has a property that is a reference
                        back to the parent
        :param link: Nested for additional links to children of this child resource
        """
        self.type_: str = type_
        self.params: str | None = params
        self.link: list[GraphDefinitionLink] | None = link

    def to_dict(self) -> dict[str, Any]:
        my_dict: dict[str, Any] = {"type": self.type_}
        if self.params:
            my_dict["params"] = self.params
        if self.link:
            my_dict["link"] = [link.to_dict() for link in self.link]
        return my_dict

    @classmethod
    def from_dict(cls, dictionary: dict[str, Any]) -> "GraphDefinitionTarget":
        type_ = dictionary.get("type")
        assert type_
        return GraphDefinitionTarget(
            type_=type_,
            params=dictionary.get("params"),
            link=[GraphDefinitionLink.from_dict(link) for link in dictionary.get("link", [])],
        )


class GraphDefinitionLink:
    def __init__(self, *, path: str | None = None, target: list[GraphDefinitionTarget]):
        """
        Create a link to another resource

        :param path: Optional path for forward links i.e., the parent resource has a property that is a reference
                        to this related resource
        :param target: list of targeted resources.
        """
        self.path: str | None = path
        self.target: list[GraphDefinitionTarget] = target

    def to_dict(self) -> dict[str, Any]:
        """
        Returns this object as a dictionary
        """
        my_dict: dict[str, Any] = {"target": [target.to_dict() for target in self.target]}
        if self.path:
            my_dict["path"] = self.path
        return my_dict

    @classmethod
    def from_dict(cls, dictionary: dict[str, Any]) -> "GraphDefinitionLink":
        return GraphDefinitionLink(
            path=dictionary.get("path"),
            target=[GraphDefinitionTarget.from_dict(target) for target in dictionary.get("target", [])],
        )


class GraphDefinition:
    def __init__(self, *, id_: str, name: str, start: str, link: list[GraphDefinitionLink]):
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
        self.link: list[GraphDefinitionLink] = link

    def to_dict(self) -> dict[str, Any]:
        """
        Returns this object as a dictionary
        """
        my_dict: dict[str, Any] = {
            "resourceType": self.resourceType,
            "id": self.id_,
            "name": self.name,
            "status": "active",
            "start": self.start,
            "link": [link.to_dict() for link in self.link],
        }
        return my_dict

    @classmethod
    def from_dict(cls, dictionary: dict[str, Any]) -> "GraphDefinition":
        id_ = dictionary.get("id")
        assert id_
        name = dictionary.get("name")
        assert name
        start = dictionary.get("start")
        assert start
        return GraphDefinition(
            id_=id_,
            name=name,
            start=start,
            link=[GraphDefinitionLink.from_dict(link) for link in dictionary.get("link", [])],
        )
