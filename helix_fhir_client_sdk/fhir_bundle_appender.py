import json
from typing import List, Optional, Dict, Any, Callable

from helix_fhir_client_sdk.fhir_bundle import (
    Bundle,
    BundleEntry,
    BundleEntryRequest,
    BundleEntryResponse,
)
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


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
        bundle_entries: List[BundleEntry] = []
        for response in responses:
            bundle_entries_for_response: List[BundleEntry] = (
                FhirBundleAppender.add_operation_outcomes(response=response)
            )
            bundle_entries.extend(bundle_entries_for_response)

        bundle.entry = bundle_entries
        return bundle

    @staticmethod
    def add_operation_outcomes(*, response: FhirGetResponse) -> List[BundleEntry]:
        bundle_entries: List[BundleEntry] = response.get_bundle_entries()
        response_url = response.url
        diagnostics_coding_nullable: List[Optional[Dict[str, Any]]] = [
            (
                {
                    "system": "https://www.icanbwell.com/url",
                    "code": response.url,
                }
                if response.url
                else None
            ),
            (
                {
                    "system": "https://www.icanbwell.com/resourceType",
                    "code": response.resource_type,
                }
                if response.resource_type
                else None
            ),
            (
                {
                    "system": "https://www.icanbwell.com/id",
                    "code": (
                        ",".join(response.id_)
                        if isinstance(response.id_, list)
                        else response.id_
                    ),
                }
                if response.id_
                else None
            ),
            {
                "system": "https://www.icanbwell.com/statuscode",
                "code": response.status,
            },
            (
                {
                    "system": "https://www.icanbwell.com/accessToken",
                    "code": response.access_token,
                }
                if response.access_token
                else None
            ),
        ]
        diagnostics_coding: List[Dict[str, Any]] = [
            c for c in diagnostics_coding_nullable if c is not None
        ]

        bundle_entry: BundleEntry
        for bundle_entry in bundle_entries:
            if (
                bundle_entry.resource
                and bundle_entry.resource.get("resourceType") == "OperationOutcome"
            ):
                # This is an OperationOutcome resource so we need to add the diagnostics to it
                bundle_entry.resource = Bundle.add_diagnostics_to_operation_outcomes(
                    resource=bundle_entry.resource,
                    diagnostics_coding=diagnostics_coding,
                )

        # now add a bundle entry for errors
        if response.error and len(bundle_entries) == 0:
            operation_outcome: Dict[str, Any] = {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": (
                            "expired"
                            if response.status == 401
                            else (
                                "not-found" if response.status == 404 else "exception"
                            )
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
            bundle_entries.append(
                BundleEntry(
                    request=BundleEntryRequest(url=response_url),
                    response=BundleEntryResponse(
                        status=str(response.status),
                        lastModified=response.lastModified,
                        etag=response.etag,
                    ),
                    resource=operation_outcome,
                )
            )
        return bundle_entries

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

    @staticmethod
    def sort_resources(
        *, bundle: Bundle, fn_sort: Callable[[BundleEntry], str] | None = None
    ) -> Bundle:
        """
        Sorts the resources in the bundle

        :param bundle: The bundle to sort
        :param fn_sort: The function to use to sort the resources (Optional).  if not provided, the resources will be sorted by resourceType/id
        """
        if not bundle.entry:
            return bundle
        if not fn_sort:
            fn_sort = lambda e: (
                (e.resource.get("resourceType", "") + "/" + e.resource.get("id", ""))
                if e.resource
                else ""
            )
        bundle.entry = sorted(
            bundle.entry,
            key=fn_sort,
        )
        return bundle
