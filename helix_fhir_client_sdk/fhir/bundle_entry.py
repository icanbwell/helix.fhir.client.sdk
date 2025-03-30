from typing import Any, Dict, Optional

from helix_fhir_client_sdk.fhir.bundle_entry_request import BundleEntryRequest
from helix_fhir_client_sdk.fhir.bundle_entry_response import BundleEntryResponse


class BundleEntry:
    # noinspection PyPep8Naming
    def __init__(
        self,
        *,
        fullUrl: Optional[str] = None,
        resource: Optional[Dict[str, Any]],
        request: Optional[BundleEntryRequest],
        response: Optional[BundleEntryResponse],
    ) -> None:
        self.resource: Optional[Dict[str, Any]] = resource
        self.request: Optional[BundleEntryRequest] = request
        self.response: Optional[BundleEntryResponse] = response
        self.fullUrl: Optional[str] = fullUrl

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if self.fullUrl is not None:
            result["fullUrl"] = self.fullUrl
        if self.resource is not None:
            result["resource"] = self.resource
        if self.request is not None:
            result["request"] = self.request.to_dict()
        if self.response is not None:
            result["response"] = self.response.to_dict()
        return result

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BundleEntry":
        return BundleEntry(
            fullUrl=d["fullUrl"] if "fullUrl" in d else None,
            resource=d["resource"] if "resource" in d else None,
            request=(
                BundleEntryRequest.from_dict(d["request"]) if "request" in d else None
            ),
            response=(
                BundleEntryResponse.from_dict(d["response"])
                if "response" in d
                else None
            ),
        )

    def __repr__(self) -> str:
        """
        Returns a string representation of the BundleEntry object.

        :return: A string representation of the BundleEntry.
        """
        return f"resource={self.resource}"
