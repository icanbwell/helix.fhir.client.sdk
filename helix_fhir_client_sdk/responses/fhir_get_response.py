import json
from typing import Optional, Dict, Any, List, Union, cast


class FhirGetResponse:
    def __init__(
        self,
        *,
        request_id: Optional[str],
        url: str,
        responses: str,
        error: Optional[str],
        access_token: Optional[str],
        total_count: Optional[int],
        status: int,
        next_url: Optional[str] = None,
        extra_context_to_return: Optional[Dict[str, Any]],
        resource_type: Optional[str],
        id_: Optional[Union[List[str], str]],
    ) -> None:
        """
        Class that encapsulates the response from FHIR server

        :param request_id: request id
        :param resource_type: (Optional)
        :param id_: (Optional)
        :param url: url that was being accessed
        :param responses: response text
        :param error: Any error returned by FHIR server
        :param access_token: access token that was used
        :param total_count: count of total records that match the provided query.
                            Only set if include_total_count was set to avoid expensive operation by server.
        :param extra_context_to_return: a dict to return with every row (separate_bundle_resources is set)
                                        or with FhirGetResponse
        """
        self.id_: Optional[Union[List[str], str]] = id_
        self.resource_type: Optional[str] = resource_type
        self.request_id: Optional[str] = request_id
        self.url: str = url
        self.responses: str = responses
        self.error: Optional[str] = error
        self.access_token: Optional[str] = access_token
        self.total_count: Optional[int] = total_count
        self.status: int = status
        self.next_url: Optional[str] = next_url
        self.extra_context_to_return: Optional[Dict[str, Any]] = extra_context_to_return
        self.successful: bool = status != 200

    def append(self, other: List["FhirGetResponse"]) -> "FhirGetResponse":
        resources = self.get_resources()
        for other_response in other:
            if other_response.responses:
                other_resources = other_response.get_resources()
                resources.extend(other_resources)
        bundle = {
            "resourceType": "Bundle",
            "entry": [{"resource": r for r in resources}],
        }
        self.responses = json.dumps(bundle)
        return self

    def get_resources(self) -> List[Dict[str, Any]]:
        if not self.responses:
            return []
        child_response_resources: Union[
            Dict[str, Any], List[Dict[str, Any]]
        ] = self.parse_json(self.responses)
        if isinstance(child_response_resources, list):
            return child_response_resources

        if "entry" in child_response_resources:
            # bundle
            child_response_resources = [
                e["resource"] for e in child_response_resources["entry"]
            ]
            return child_response_resources
        else:
            return [child_response_resources]

    @staticmethod
    def parse_json(responses: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if responses is None or len(responses) == 0:
            return {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "exception",
                        "diagnostics": "Content was empty",
                    }
                ],
            }

        try:
            return cast(
                Union[Dict[str, Any], List[Dict[str, Any]]], json.loads(responses)
            )
        except json.decoder.JSONDecodeError as e:
            return {
                "resourceType": "OperationOutcome",
                "issue": [
                    {"severity": "error", "code": "exception", "diagnostics": str(e)}
                ],
            }

    def __repr__(self) -> str:
        instance_variables_text = str(vars(self))
        return f"FhirGetResponse: {instance_variables_text}"
