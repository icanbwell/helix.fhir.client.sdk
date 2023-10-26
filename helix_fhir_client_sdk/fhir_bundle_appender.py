import json
from typing import List, Optional, Dict, Any, Union

from helix_fhir_client_sdk.fhir_bundle import (
    Bundle,
    BundleEntry,
    BundleEntryRequest,
    BundleEntryResponse,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from helix_fhir_client_sdk.utilities.json_helpers import FhirClientJsonHelpers


class FhirBundleAppender:
    """
    This class appends responses to a bundle


    """

    @staticmethod
    def append_responses(*, responses: List[FhirGetResponse], bundle: Bundle) -> Bundle:
        """
        Appends responses to the bundle.  If there was an error then it appends OperationOutcome resources to the bundle


        :param responses: The responses to append
        :param bundle: The bundle to append to
        :return: The bundle with the responses appended
        """
        response: FhirGetResponse
        for response in responses:
            response_text = response.responses
            response_url = response.url
            if response_text or response.error:
                if not bundle.entry:
                    bundle.entry = []
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
                    bundle.entry.extend(
                        [
                            BundleEntry(
                                request=BundleEntryRequest(url=response_url),
                                response=BundleEntryResponse(
                                    status=str(response.status),
                                    lastModified=response.lastModified,
                                    etag=response.etag,
                                ),
                                resource=bundle.add_diagnostics_to_operation_outcomes(
                                    resource=r, diagnostics_coding=diagnostics_coding
                                ),
                            )
                            for r in response_json
                        ]
                    )
                elif response_json.get("entry"):
                    bundle.entry.extend(
                        [
                            BundleEntry(
                                request=BundleEntryRequest(url=response_url),
                                response=BundleEntryResponse(
                                    status=str(response.status),
                                    lastModified=response.lastModified,
                                    etag=response.etag,
                                ),
                                resource=bundle.add_diagnostics_to_operation_outcomes(
                                    resource=entry["resource"],
                                    diagnostics_coding=diagnostics_coding,
                                ),
                            )
                            for entry in response_json["entry"]
                        ]
                    )
                else:
                    bundle.entry.append(
                        BundleEntry(
                            request=BundleEntryRequest(url=response_url),
                            response=BundleEntryResponse(
                                status=str(response.status),
                                lastModified=response.lastModified,
                                etag=response.etag,
                            ),
                            resource=response_json,
                        )
                    )
        return bundle

    @staticmethod
    def remove_duplicate_resources(*, bundle: Bundle) -> Bundle:
        """
        Removes duplicate resources from the bundle

        :param bundle: The bundle to remove duplicates from
        :return: The bundle with duplicates removed
        """
        if not bundle.entry:
            return bundle
        bundle_entries: List[BundleEntry] = bundle.entry
        unique_bundle_entries: List[BundleEntry] = list(
            {
                f'{e.resource["resourceType"]}/{e.resource["id"]}': e
                for e in bundle_entries
                if e.resource
                and e.resource.get("resourceType")
                and e.resource.get("id")
            }.values()
        )
        null_id_bundle_entries: List[BundleEntry] = [
            e for e in bundle_entries if not e.resource or not e.resource.get("id")
        ]
        unique_bundle_entries.extend(null_id_bundle_entries)
        bundle.entry = unique_bundle_entries

        return bundle
