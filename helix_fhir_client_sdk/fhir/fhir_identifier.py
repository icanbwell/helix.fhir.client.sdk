import json
from typing import Optional, Dict, Any


class FhirIdentifier:
    """
    FHIR Identifier class for representing identifiers in FHIR resources.
    """

    __slots__ = ["use", "system", "value"]

    def __init__(
        self,
        use: Optional[str] = None,
        system: Optional[str] = None,
        value: Optional[str] = None,
    ) -> None:
        """
        Initialize the FhirIdentifier object.

        :param use: The purpose of the identifier (e.g., official, secondary).
        :param system: The namespace for the identifier.
        :param value: The actual identifier value.
        """
        self.use: Optional[str] = use
        self.system: Optional[str] = system
        self.value: Optional[str] = value

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the FhirIdentifier object to a dictionary.

        :return: A dictionary representation of the FhirIdentifier object.
        """
        return {
            "use": self.use,
            "system": self.system,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FhirIdentifier":
        """
        Create a FhirIdentifier object from a dictionary.

        :param data: A dictionary containing the identifier data.
        :return: An instance of FhirIdentifier.
        """
        return cls(
            use=data.get("use"),
            system=data.get("system"),
            value=data.get("value"),
        )

    def to_json(self) -> str:
        """
        Convert the FhirIdentifier object to a JSON string.
        :return: A JSON string representation of the FhirIdentifier object.
        """
        return json.dumps(self.to_dict())

    def __repr__(self) -> str:
        """
        Return a string representation of the FhirIdentifier object.
        :return: A string representation of the FhirIdentifier object.
        """
        return (
            f"FhirIdentifier(use={self.use}, system={self.system}, value={self.value})"
        )

    def copy(self) -> "FhirIdentifier":
        """
        Create a copy of the FhirIdentifier object.

        :return: A new FhirIdentifier object with the same attributes.
        """
        return FhirIdentifier(use=self.use, system=self.system, value=self.value)
