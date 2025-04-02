import json
from typing import Optional, Dict, Any, OrderedDict

from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class FhirBundleEntrySearch:
    """
    FhirBundleEntrySearch is a class that represents a search entry in a FHIR Bundle.
    It contains the resource, search mode, and search parameters.
    """

    __slots__ = ["mode", "score"]

    def __init__(self, *, mode: Optional[str], score: Optional[float]) -> None:
        """
        Initializes the FhirBundleEntrySearch with the given parameters.

        """
        self.mode: Optional[str] = mode
        self.score: Optional[float] = score

    def to_dict(self) -> OrderedDict[str, Any]:
        """
        Converts the FhirBundleEntrySearch instance to a dictionary.

        :return: A dictionary representation of the FhirBundleEntrySearch instance.
        """
        result: OrderedDict[str, Any] = OrderedDict[str, Any]()
        if self.mode is not None:
            result["mode"] = self.mode
        if self.score is not None:
            result["score"] = self.score

        return result

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any] | OrderedDict[str, Any]
    ) -> "FhirBundleEntrySearch":
        """
        Creates a FhirBundleEntrySearch object from a dictionary.

        :param data: A dictionary containing the search entry data.
        :return: An instance of FhirBundleEntrySearch.
        """
        return cls(
            mode=data.get("mode"),
            score=data.get("score"),
        )

    def to_json(self) -> str:
        """
        Converts the FhirBundleEntrySearch instance to a JSON string.

        :return: A JSON string representation of the FhirBundleEntrySearch instance.
        """
        return json.dumps(self.to_dict(), cls=FhirJSONEncoder)

    def __repr__(self) -> str:
        """
        Returns a string representation of the FhirBundleEntrySearch instance.

        :return: A string representation of the FhirBundleEntrySearch instance.
        """
        return f"FhirBundleEntrySearch(mode={self.mode}, score={self.score})"

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FhirBundleEntrySearch":
        """
        Creates a copy of the FhirBundleEntrySearch instance.

        :return: A new FhirBundleEntrySearch instance with the same attributes.
        """
        return FhirBundleEntrySearch(mode=self.mode, score=self.score)
