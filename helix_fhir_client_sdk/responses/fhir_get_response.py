import json
from datetime import datetime

# noinspection PyPackageRequirements
from dateutil import parser
from typing import Optional, Dict, Any, List, Union, cast, AsyncGenerator

from helix_fhir_client_sdk.fhir_bundle import (
    BundleEntry,
    BundleEntryRequest,
    BundleEntryResponse,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder
from helix_fhir_client_sdk.utilities.retryable_aiohttp_url_result import (
    RetryableAioHttpUrlResult,
)


class FhirGetResponse:
    """
    This class represents a response from a FHIR server.
    NOTE: This class does converted to a Row in Spark so keep all the property types simple python types


    """

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
        response_headers: Optional[
            List[str]
        ],  # header name and value separated by a colon
        chunk_number: Optional[int] = None,
        cache_hits: Optional[int] = None,
        results_by_url: List[RetryableAioHttpUrlResult],
    ) -> None:
        """
        Class that encapsulates the response from FHIR server
        NOTE: This class does converted to a Row in Spark so keep all the property types simple python types

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
        :param status: status code
        :param next_url: next url to use for pagination
        :param response_headers: headers returned by the server (can have duplicate header names)
        :param chunk_number: chunk number for streaming
        :param cache_hits: count of cache hits
        :param results_by_url: results by url
        :return: None
        """
        self.id_: Optional[Union[List[str], str]] = id_
        self.resource_type: Optional[str] = resource_type
        self.request_id: Optional[str] = request_id
        self.url: str = url
        """ string that holds the response from the fhir server """
        self.responses: str = responses
        self.error: Optional[str] = error
        """ Any error returned by the fhir server """
        self.access_token: Optional[str] = access_token
        """ Access token used to make the request to the fhir server """
        self.total_count: Optional[int] = total_count
        """ Total count of resources returned by the fhir serer """
        self.status: int = status
        """ Status code returned by the fhir server """ ""
        self.next_url: Optional[str] = next_url
        """ Next url to use for pagination """
        self.extra_context_to_return: Optional[Dict[str, Any]] = extra_context_to_return
        """ Extra context to return with every row (separate_bundle_resources is set) or with FhirGetResponse"""
        self.successful: bool = status == 200
        """ True if the request was successful """
        self.response_headers: Optional[List[str]] = response_headers
        """ Headers returned by the server (can have duplicate header names) """ ""
        self.chunk_number: Optional[int] = chunk_number
        """ Chunk number for streaming """
        self.cache_hits: Optional[int] = cache_hits
        """ Count of cache hits """
        self.results_by_url: List[RetryableAioHttpUrlResult] = results_by_url
        """ Count of errors in the response by status """

    def append(self, other_response: "FhirGetResponse") -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param other_response: FhirGetResponse object to append to current one
        :return: self
        """
        parse_bundle = False
        other_response_json = other_response.parse_json(other_response.responses)
        if isinstance(other_response_json, list):
            # in case when expand_fhir_bundle is True, there will definitely be a key with entry in the response,
            # it will be empty when there is no data on fhir associated to the filter passed.
            if len(other_response_json) > 0 and "entry" in other_response_json[0]:
                parse_bundle = True
        elif "entry" in other_response_json:
            parse_bundle = True

        if parse_bundle:
            bundle_entries: List[BundleEntry] = self.get_bundle_entries()
            if other_response.responses:
                other_bundle_entries: List[BundleEntry] = (
                    other_response.get_bundle_entries()
                )
                bundle_entries.extend(other_bundle_entries)
            bundle = {
                "resourceType": "Bundle",
                "entry": bundle_entries,
            }
            self.responses = json.dumps(bundle, cls=FhirJSONEncoder)
        else:
            responses_json = self.parse_json(self.responses)
            if not isinstance(responses_json, list):
                responses_json = [responses_json]
            if isinstance(other_response_json, list):
                responses_json.extend(other_response_json)
            else:
                responses_json.append(other_response_json)
            self.responses = json.dumps(responses_json, cls=FhirJSONEncoder)
        if other_response.chunk_number and (other_response.chunk_number or 0) > (
            self.chunk_number or 0
        ):
            self.chunk_number = other_response.chunk_number
        if other_response.next_url:
            self.next_url = other_response.next_url
            self.access_token = other_response.access_token
        self.cache_hits = (self.cache_hits or 0) + (other_response.cache_hits or 0)

        if other_response.results_by_url:
            if self.results_by_url is None:
                self.results_by_url = other_response.results_by_url
            else:
                self.results_by_url.extend(other_response.results_by_url)

        return self

    def extend(self, others: List["FhirGetResponse"]) -> "FhirGetResponse":
        """
        Append the responses from other to self

        :param others: list of FhirGetResponse objects
        :return: self
        """
        bundle_entries: List[BundleEntry] = self.get_bundle_entries()
        for other_response in others:
            if other_response.responses:
                other_bundle_entries: List[BundleEntry] = (
                    other_response.get_bundle_entries()
                )
                bundle_entries.extend(other_bundle_entries)
        bundle = {
            "resourceType": "Bundle",
            "entry": bundle_entries,
        }
        self.responses = json.dumps(bundle, cls=FhirJSONEncoder)
        latest_chunk_number: List[int] = sorted(
            [o.chunk_number for o in others if o.chunk_number], reverse=True
        )
        if len(latest_chunk_number) > 0:
            self.chunk_number = latest_chunk_number[0]
        if len(others) > 0:
            self.next_url = others[-1].next_url
            self.access_token = others[-1].access_token
        self.cache_hits = sum(
            [r.cache_hits if r.cache_hits is not None else 0 for r in others]
        )
        for other_response in others:
            if other_response.results_by_url:
                if self.results_by_url is None:
                    self.results_by_url = other_response.results_by_url
                else:
                    self.results_by_url.extend(other_response.results_by_url)

        return self

    def get_resources(self) -> List[Dict[str, Any]]:
        """
        Gets the resources from the response


        :return: list of resources
        """
        if not self.responses:
            return []

        try:
            # THis is either a list of resources or a Bundle resource containing a list of resources
            child_response_resources: Union[Dict[str, Any], List[Dict[str, Any]]] = (
                self.parse_json(self.responses)
            )
            # if it is a list of resources then return it
            if isinstance(child_response_resources, list):
                return [
                    cast(Dict[str, Any], c.get("resource")) if "resource" in c else c
                    for c in child_response_resources
                ]
            # otherwise it is a bundle so parse out the resources
            if "entry" in child_response_resources:
                # bundle
                child_response_resources = [
                    e["resource"] for e in child_response_resources["entry"]
                ]
                return child_response_resources
            else:
                return [child_response_resources]
        except Exception as e:
            raise Exception(f"Could not get resources from: {self.responses}") from e

    def get_bundle_entries(self) -> List[BundleEntry]:
        """
        Gets the Bundle entries from the response


        :return: list of bundle entries
        """
        if not self.responses:
            return []
        try:
            # THis is either a list of resources or a Bundle resource containing a list of resources
            child_response_resources: Union[Dict[str, Any], List[Dict[str, Any]]] = (
                self.parse_json(self.responses)
            )

            # use these if the bundle entry does not have them
            request: BundleEntryRequest = BundleEntryRequest(url=self.url)
            response: BundleEntryResponse = BundleEntryResponse(
                status=str(self.status),
                lastModified=self.lastModified,
                etag=self.etag,
            )
            # if it is a list of resources then wrap them in a bundle entry and return them
            if isinstance(child_response_resources, list):
                return [
                    BundleEntry(resource=r, request=request, response=response)
                    for r in child_response_resources
                ]
            # otherwise it is a bundle so parse out the resources
            if "entry" in child_response_resources:
                bundle_entries: List[Dict[str, Any]] = child_response_resources["entry"]
                return [
                    BundleEntry(
                        resource=entry["resource"],
                        request=(
                            BundleEntryRequest.from_dict(
                                cast(Dict[str, Any], entry.get("request"))
                            )
                            if entry.get("request")
                            and isinstance(entry.get("request"), dict)
                            else request
                        ),
                        response=(
                            BundleEntryResponse.from_dict(
                                cast(Dict[str, Any], entry.get("response"))
                            )
                            if entry.get("response")
                            and isinstance(entry.get("response"), dict)
                            else response
                        ),
                        fullUrl=entry.get("fullUrl"),
                    )
                    for entry in bundle_entries
                ]
            else:
                return [
                    BundleEntry(
                        resource=child_response_resources,
                        request=request,
                        response=response,
                    )
                ]
        except Exception as e:
            raise Exception(
                f"Could not get bundle entries from: {self.responses}"
            ) from e

    @staticmethod
    def parse_json(responses: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Parses the json response from the fhir server


        :param responses: response from the fhir server
        :return: one of:
        1. response_resources is a list of resources
        2. response_resources is a bundle with a list of resources
        3. response_resources is a single resource
        """
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

    # noinspection PyPep8Naming
    @property
    def lastModified(self) -> Optional[datetime]:
        """
        Returns the last modified date from the response headers

        :return: last modified date
        """
        if self.response_headers is None:
            return None
        header: str
        for header in self.response_headers:
            header_name: str = header.split(":")[0].strip()
            header_value: str = header.split(":")[1].strip()
            if header_name == "Last-Modified":
                last_modified_str: Optional[str] = header_value
                if last_modified_str is None:
                    return None
                if isinstance(last_modified_str, datetime):
                    return last_modified_str

                try:
                    last_modified_datetime: datetime = parser.parse(last_modified_str)
                    return last_modified_datetime
                except ValueError:
                    return None
        return None

    @property
    def etag(self) -> Optional[str]:
        """
        Returns the etag from the response headers

        :return: etag
        """
        if self.response_headers is None:
            return None
        header: str
        for header in self.response_headers:
            if ":" not in header:
                continue
            header_name: str = header.split(":")[0].strip()
            header_value: str = header.split(":")[1].strip()
            if header_name == "ETag":
                return header_value
        return None

    def remove_duplicates(self) -> None:
        """
        removes duplicate resources from the response i.e., resources with same resourceType and id

        """
        try:
            response_resources: Union[Dict[str, Any], List[Dict[str, Any]]] = (
                self.parse_json(self.responses)
            )

            # there are three cases:
            # 1. response_resources is a list of resources
            # 2. response_resources is a bundle with a list of resources
            # 3. response_resources is a single resource

            if isinstance(response_resources, list):
                # if it is a list of resources then find unique resources
                unique_resources: List[Dict[str, Any]] = list(
                    {
                        f'{r.get("resourceType")}/{r.get("id")}': r
                        for r in response_resources
                        if r.get("resourceType") and r.get("id")
                    }.values()
                )
                null_id_resources: List[Dict[str, Any]] = [
                    r for r in response_resources if not r.get("id")
                ]
                unique_resources.extend(null_id_resources)
                self.responses = json.dumps(unique_resources, cls=FhirJSONEncoder)
            elif "entry" in response_resources:
                # otherwise it is a bundle so parse out the resources
                bundle_entries: List[Dict[str, Any]] = response_resources["entry"]
                unique_bundle_entries = list(
                    {
                        f'{e["resource"]["resourceType"]}/{e["resource"]["id"]}': e
                        for e in bundle_entries
                        if e.get("resource")
                        and e["resource"].get("resourceType")
                        and e["resource"].get("id")
                    }.values()
                )
                null_id_bundle_entries: List[Dict[str, Any]] = [
                    e
                    for e in bundle_entries
                    if not e.get("resource") or not e["resource"].get("id")
                ]
                unique_bundle_entries.extend(null_id_bundle_entries)
                response_resources["entry"] = unique_bundle_entries
                self.responses = json.dumps(response_resources, cls=FhirJSONEncoder)
            else:
                # since this is a single resource there is no need to find duplicates
                return
        except Exception as e:
            raise Exception(f"Could not get parse json from: {self.responses}") from e

    def get_resource_type_and_ids(self) -> List[str]:
        """
        Gets the ids of the resources from the response
        """
        resources: List[Dict[str, Any]] = self.get_resources()
        try:
            return [f"{r.get('resourceType')}/{r.get('id')}" for r in resources]
        except Exception as e:
            raise Exception(
                f"Could not get resourceType and id from resources: {json.dumps(resources, cls=FhirJSONEncoder)}"
            ) from e

    @classmethod
    async def from_async_generator(
        cls, generator: AsyncGenerator["FhirGetResponse", None]
    ) -> Optional["FhirGetResponse"]:
        """
        Reads a generator of FhirGetResponse and returns a single FhirGetResponse by appending all the FhirGetResponse

        :param generator: generator of FhirGetResponse items
        :return: FhirGetResponse
        """
        result: FhirGetResponse | None = None
        async for value in generator:
            if not result:
                result = value
            else:
                result.append(value)

        assert result
        return result

    def get_operation_outcomes(self) -> List[Dict[str, Any]]:
        """
        Gets the operation outcomes from the response

        :return: list of operation outcomes
        """
        return [
            r
            for r in self.get_resources()
            if r.get("resourceType") == "OperationOutcome"
        ]

    def get_resources_except_operation_outcomes(self) -> List[Dict[str, Any]]:
        """
        Gets the normal FHIR resources by skipping any OperationOutcome resources

        :return: list of valid resources
        """
        return [
            r
            for r in self.get_resources()
            if r.get("resourceType") != "OperationOutcome"
        ]

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary

        :return: dictionary
        """
        return self.__dict__
