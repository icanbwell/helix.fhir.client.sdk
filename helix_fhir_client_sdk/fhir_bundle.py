from datetime import datetime
from typing import Any, Dict, List, Optional


class BundleEntryRequest:
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
            ifModifiedSince=datetime.fromisoformat(d["ifModifiedSince"])
            if "ifModifiedSince" in d
            else None,
            ifNoneMatch=d["ifNoneMatch"] if "ifNoneMatch" in d else None,
        )


class BundleEntryResponse:
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
            lastModified=datetime.fromisoformat(d["lastModified"])
            if "lastModified" in d
            else None,
            etag=d["etag"] if "etag" in d else None,
        )


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
            request=BundleEntryRequest.from_dict(d["request"])
            if "request" in d
            else None,
            response=BundleEntryResponse.from_dict(d["response"])
            if "response" in d
            else None,
        )


class Bundle:
    def __init__(self, *, entry: Optional[List[BundleEntry]] = None) -> None:
        self.entry: Optional[List[BundleEntry]] = entry

    def to_dict(self) -> Dict[str, Any]:
        if self.entry:
            return {"entry": [entry.to_dict() for entry in self.entry]}
        else:
            return {}

    @staticmethod
    def add_diagnostics_to_operation_outcomes(
        *, resource: Dict[str, Any], diagnostics_coding: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Adds diagnostic coding to OperationOutcome resources to identify which call resulted in that OperationOutcome
        being returned by the server


        :param resource: The resource to add the diagnostics to
        :param diagnostics_coding: The diagnostics coding to add
        :return: The resource with the diagnostics added
        """
        if resource.get("resourceType") == "OperationOutcome":
            if resource.get("issue"):
                for issue in resource["issue"]:
                    details: Dict[str, Any] = issue.get("details")
                    if details is None:
                        issue["details"] = {}
                        details = issue["details"]
                    coding: Optional[List[Dict[str, Any]]] = details.get("coding")
                    if coding is None:
                        details["coding"] = []
                        coding = details["coding"]
                    assert coding is not None
                    coding.extend(diagnostics_coding)
        return resource
