from datetime import datetime
from typing import Any, Dict, Optional, OrderedDict


class FhirBundleEntryRequest:
    """
    FHIR Bundle Entry Request class for encapsulating the request to be sent to FHIR server
    """

    __slots__ = ["url", "method", "ifModifiedSince", "ifNoneMatch", "ifNoneExist"]

    # noinspection PyPep8Naming
    def __init__(
        self,
        *,
        url: str,
        method: str = "GET",
        ifNoneMatch: Optional[str] = None,
        ifModifiedSince: Optional[datetime] = None,
        ifNoneExist: Optional[str] = None,
    ) -> None:
        self.url: str = url
        self.method: str = method
        self.ifModifiedSince: Optional[datetime] = ifModifiedSince
        self.ifNoneMatch: Optional[str] = ifNoneMatch
        self.ifNoneExist: Optional[str] = ifNoneExist

    def to_dict(self) -> OrderedDict[str, Any]:
        result: OrderedDict[str, Any] = OrderedDict[str, Any](
            {"url": self.url, "method": self.method}
        )
        if self.ifModifiedSince is not None:
            result["ifModifiedSince"] = self.ifModifiedSince.isoformat()
        if self.ifNoneMatch is not None:
            result["ifNoneMatch"] = self.ifNoneMatch
        if self.ifNoneExist is not None:
            result["ifNoneExist"] = self.ifNoneExist
        return result

    @classmethod
    def from_dict(
        cls, d: Dict[str, Any] | OrderedDict[str, Any]
    ) -> "FhirBundleEntryRequest":
        return cls(
            url=d["url"],
            method=d["method"],
            ifModifiedSince=(
                datetime.fromisoformat(d["ifModifiedSince"])
                if "ifModifiedSince" in d
                else None
            ),
            ifNoneMatch=d["ifNoneMatch"] if "ifNoneMatch" in d else None,
            ifNoneExist=d["ifNoneExist"] if "ifNoneExist" in d else None,
        )

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FhirBundleEntryRequest":
        return FhirBundleEntryRequest(
            url=self.url,
            method=self.method,
            ifModifiedSince=self.ifModifiedSince,
            ifNoneMatch=self.ifNoneMatch,
            ifNoneExist=self.ifNoneExist,
        )

    def __repr__(self) -> str:
        return (
            f"FhirBundleEntryRequest(url={self.url}, method={self.method}, "
            f"ifModifiedSince={self.ifModifiedSince}, ifNoneMatch={self.ifNoneMatch})"
        )
