import json
from typing import Any, Dict, List, Optional, Union

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.json_helpers import FhirClientJsonHelpers


class BundleEntry:
    def __init__(self, resource: Optional[Dict[str, Any]] = None) -> None:
        self.resource: Optional[Dict[str, Any]] = resource

    def to_dict(self) -> Dict[str, Any]:
        return {"resource": self.resource}


class Bundle:
    def __init__(self, entry: Optional[List[BundleEntry]] = None) -> None:
        self.entry: Optional[List[BundleEntry]] = entry

    def append_responses(self, responses: List[FhirGetResponse]) -> "Bundle":
        response: FhirGetResponse
        for response in responses:
            response_text = response.responses
            if response_text or response.error:
                if not self.entry:
                    self.entry = []
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
                                "details": {
                                    "coding": [
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
                                },
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
                response_json = FhirClientJsonHelpers.remove_empty_elements(
                    response_json
                )
                if isinstance(response_json, list):
                    self.entry.extend([BundleEntry(resource=r) for r in response_json])
                elif response_json.get("entry"):
                    self.entry.extend(
                        [
                            BundleEntry(resource=entry["resource"])
                            for entry in response_json["entry"]
                        ]
                    )
                else:
                    self.entry.append(BundleEntry(resource=response_json))
        return self

    def to_dict(self) -> Dict[str, Any]:
        if self.entry:
            return {"entry": [entry.to_dict() for entry in self.entry]}
        else:
            return {}
