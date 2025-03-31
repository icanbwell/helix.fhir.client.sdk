from datetime import datetime
from typing import Any, Dict, Optional


class BundleEntryRequest:
    __slots__ = ["url", "method", "ifModifiedSince", "ifNoneMatch"]

    # noinspection PyPep8Naming
    def __init__(
        self,
        *,
        url: str,
        method: str = "GET",
        ifNoneMatch: Optional[str] = None,
        ifModifiedSince: Optional[datetime] = None,
    ) -> None:
        self.url: str = url
        self.method: str = method
        self.ifModifiedSince: Optional[datetime] = ifModifiedSince
        self.ifNoneMatch: Optional[str] = ifNoneMatch

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"url": self.url, "method": self.method}
        if self.ifModifiedSince is not None:
            result["ifModifiedSince"] = self.ifModifiedSince.isoformat()
        if self.ifNoneMatch is not None:
            result["ifNoneMatch"] = self.ifNoneMatch
        return result

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BundleEntryRequest":
        return BundleEntryRequest(
            url=d["url"],
            method=d["method"],
            ifModifiedSince=(
                datetime.fromisoformat(d["ifModifiedSince"])
                if "ifModifiedSince" in d
                else None
            ),
            ifNoneMatch=d["ifNoneMatch"] if "ifNoneMatch" in d else None,
        )
