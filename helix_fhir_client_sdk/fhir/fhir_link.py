import json
from typing import Any, Dict, OrderedDict

from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class FhirLink:
    """
    Represents a link in a FHIR
    """

    __slots__ = ["url", "relation"]

    def __init__(self, *, url: str, relation: str) -> None:
        """
        Initializes a FhirLink instance.

        :param url: The URL of the link.
        :param relation: The relation type of the link.
        """
        self.url: str = url
        self.relation: str = relation

    def to_dict(self) -> OrderedDict[str, Any]:
        """
        Converts the FhirLink instance to a dictionary.

        :return: A dictionary representation of the link.
        """
        return OrderedDict[str, Any]({"url": self.url, "relation": self.relation})

    def to_json(self) -> str:
        """
        Converts the FhirLink instance to a JSON string.

        :return: A JSON string representation of the link.
        """
        return json.dumps(self.to_dict(), cls=FhirJSONEncoder)

    def __repr__(self) -> str:
        return f"FhirLink(url={self.url}, relation={self.relation})"

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | OrderedDict[str, Any]) -> "FhirLink":
        """
        Populates the FhirLink instance from a dictionary.

        :param data: A dictionary containing the link data.
        """
        return cls(
            url=data.get("url") or "unknown",
            relation=data.get("relation") or "unknown",
        )

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FhirLink":
        """
        Creates a copy of the FhirLink instance.

        :return: A new FhirLink instance with the same attributes.
        """
        return FhirLink(url=self.url, relation=self.relation)
