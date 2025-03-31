from datetime import datetime
from typing import Any, Dict, Optional


class BundleEntryResponse:
    __slots__ = ["status", "lastModified", "etag"]

    # noinspection PyPep8Naming
    def __init__(
        self,
        *,
        status: str,
        etag: Optional[str],
        lastModified: Optional[datetime],
    ) -> None:
        self.status: str = status
        if isinstance(status, int):
            self.status = str(status)
        self.lastModified: Optional[datetime] = lastModified
        self.etag: Optional[str] = etag

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"status": self.status}
        if self.lastModified is not None:
            result["lastModified"] = self.lastModified.isoformat()
        if self.etag is not None:
            result["etag"] = self.etag
        return result

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BundleEntryResponse":
        return BundleEntryResponse(
            status=d["status"],
            lastModified=(
                datetime.fromisoformat(d["lastModified"])
                if "lastModified" in d
                else None
            ),
            etag=d["etag"] if "etag" in d else None,
        )
