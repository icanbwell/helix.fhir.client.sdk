import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.json_helpers import FhirClientJsonHelpers


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


class BundleEntryResponse:
    # noinspection PyPep8Naming
    def __init__(
        self,
        *,
        status: str,
        etag: Optional[str] = None,
        lastModified: Optional[datetime] = None,
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


class Bundle:
    def __init__(self, *, entry: Optional[List[BundleEntry]] = None) -> None:
        self.entry: Optional[List[BundleEntry]] = entry

    def append_responses(self, responses: List[FhirGetResponse]) -> "Bundle":
        """
        Appends responses to the bundle.  If there was an error then it appends OperationOutcome resources to the bundle


        :param responses: The responses to append
        :return: The bundle with the responses appended
        """
        response: FhirGetResponse
        for response in responses:
            response_text = response.responses
            response_url = response.url
            if response_text or response.error:
                if not self.entry:
                    self.entry = []
                diagnostics_coding_nullable: List[Optional[Dict[str, Any]]] = [
                    {
                        "system": "https://www.icanbwell.com/url",
                        "code": response.url,
                    }
                    if response.url
                    else None,
                    {
                        "system": "https://www.icanbwell.com/resourceType",
                        "code": response.resource_type,
                    }
                    if response.resource_type
                    else None,
                    {
                        "system": "https://www.icanbwell.com/id",
                        "code": ",".join(response.id_)
                        if isinstance(response.id_, list)
                        else response.id_,
                    }
                    if response.id_
                    else None,
                    {
                        "system": "https://www.icanbwell.com/statuscode",
                        "code": response.status,
                    },
                    {
                        "system": "https://www.icanbwell.com/accessToken",
                        "code": response.access_token,
                    }
                    if response.access_token
                    else None,
                ]
                diagnostics_coding: List[Dict[str, Any]] = [
                    c for c in diagnostics_coding_nullable if c is not None
                ]
                # Now either use the response we received or if we received an error, create an OperationOutcome
                response_json: Union[List[Dict[str, Any]], Dict[str, Any]] = (
                    json.loads(response_text)
                    if not response.error
                    else {
                        "resourceType": "OperationOutcome",
                        "issue": [
                            {
                                "severity": "error",
                                "code": (
                                    "expired"
                                    if response.status == 401
                                    else "not-found"
                                    if response.status == 404
                                    else "exception"
                                ),
                                "details": {"coding": diagnostics_coding},
                                "diagnostics": json.dumps(
                                    {
                                        "url": response.url,
                                        "error": response.error,
                                        "status": response.status,
                                        "extra_context_to_return": response.extra_context_to_return,
                                        "accessToken": response.access_token,
                                        "requestId": response.request_id,
                                        "resourceType": response.resource_type,
                                        "id": response.id_,
                                    }
                                ),
                            }
                        ],
                    }
                )

                if isinstance(response_json, str):
                    response_json = {
                        "resourceType": "OperationOutcome",
                        "issue": [
                            {
                                "severity": "error",
                                "code": (
                                    "expired"
                                    if response.status == 401
                                    else "not-found"
                                    if response.status == 404
                                    else "exception"
                                ),
                                "details": {"coding": diagnostics_coding},
                                "diagnostics": json.dumps(
                                    {
                                        "url": response.url,
                                        "error": response.error,
                                        "status": response.status,
                                        "extra_context_to_return": response.extra_context_to_return,
                                        "accessToken": response.access_token,
                                        "requestId": response.request_id,
                                        "resourceType": response.resource_type,
                                        "id": response.id_,
                                        "response_text": response_json,
                                    }
                                ),
                            }
                        ],
                    }

                response_json = FhirClientJsonHelpers.remove_empty_elements(
                    response_json
                )
                if isinstance(response_json, list):
                    self.entry.extend(
                        [
                            BundleEntry(
                                request=BundleEntryRequest(url=response_url),
                                response=BundleEntryResponse(
                                    status=str(response.status),
                                ),
                                resource=self.add_diagnostics_to_operation_outcomes(
                                    resource=r, diagnostics_coding=diagnostics_coding
                                ),
                            )
                            for r in response_json
                        ]
                    )
                elif response_json.get("entry"):
                    self.entry.extend(
                        [
                            BundleEntry(
                                request=BundleEntryRequest(url=response_url),
                                response=BundleEntryResponse(
                                    status=str(response.status),
                                ),
                                resource=self.add_diagnostics_to_operation_outcomes(
                                    resource=entry["resource"],
                                    diagnostics_coding=diagnostics_coding,
                                ),
                            )
                            for entry in response_json["entry"]
                        ]
                    )
                else:
                    self.entry.append(
                        BundleEntry(
                            request=BundleEntryRequest(url=response_url),
                            response=BundleEntryResponse(
                                status=str(response.status),
                            ),
                            resource=response_json,
                        )
                    )
        return self

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
