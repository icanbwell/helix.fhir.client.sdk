import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable

from helix_fhir_client_sdk.fhir.bundle import Bundle
from helix_fhir_client_sdk.fhir.bundle_entry import BundleEntry
from helix_fhir_client_sdk.fhir.bundle_entry_request import BundleEntryRequest
from helix_fhir_client_sdk.fhir.bundle_entry_response import BundleEntryResponse
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
                FhirBundleAppender.add_operation_outcomes_to_response(response=response)
            )
            bundle_entries.extend(bundle_entries_for_response)

        bundle.entry = bundle_entries
        return bundle

    @staticmethod
    def add_operation_outcomes_to_response(
        *, response: FhirGetResponse
    ) -> List[BundleEntry]:
        bundle_entries: List[BundleEntry] = response.get_bundle_entries()
        return FhirBundleAppender.add_operation_outcomes_to_bundle_entries(
            bundle_entries=bundle_entries,
            error=response.error,
            url=response.url,
            resource_type=response.resource_type,
            id_=response.id_,
            status=response.status,
            access_token=response.access_token,
            extra_context_to_return=response.extra_context_to_return,
            request_id=response.request_id,
            last_modified=response.lastModified,
            etag=response.etag,
        )

    @staticmethod
    def add_operation_outcomes_to_bundle_entries(
        *,
        bundle_entries: List[BundleEntry],
        error: Optional[str],
        url: str,
        resource_type: Optional[str],
        id_: Optional[str | List[str]],
        status: int,
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        request_id: Optional[str],
        last_modified: Optional[datetime],
        etag: Optional[str],
    ) -> List[BundleEntry]:
        """
        Adds operation outcomes to the bundle entries

        :param bundle_entries: The bundle entries to add operation outcomes to
        :param error: The error message
        :param url: The url of the resource
        :param resource_type: The type of resource
        :param id_: The id of the resource
        :param status: The status code
        :param access_token: The access token
        :param extra_context_to_return: Extra context to return
        :param request_id: The request id
        :param last_modified: The last modified date
        :param etag: The etag of the resource
        """
        diagnostics_coding: List[Dict[str, Any]] = (
            FhirBundleAppender.get_diagnostic_coding(
                access_token=access_token,
                url=url,
                resource_type=resource_type,
                id_=id_,
                status=status,
            )
        )

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
        if error and len(bundle_entries) == 0:
            operation_outcome: Dict[str, Any] = (
                FhirBundleAppender.create_operation_outcome_resource(
                    error=error,
                    url=url,
                    resource_type=resource_type,
                    id_=id_,
                    status=status,
                    access_token=access_token,
                    extra_context_to_return=extra_context_to_return,
                    request_id=request_id,
                )
            )
            bundle_entries.append(
                BundleEntry(
                    request=BundleEntryRequest(url=url),
                    response=BundleEntryResponse(
                        status=str(status),
                        lastModified=last_modified,
                        etag=etag,
                    ),
                    resource=operation_outcome,
                )
            )
        return bundle_entries

    @staticmethod
    def create_operation_outcome_resource(
        *,
        error: Optional[str],
        url: str,
        resource_type: Optional[str],
        id_: Optional[str | List[str]],
        status: int,
        access_token: Optional[str],
        extra_context_to_return: Optional[Dict[str, Any]],
        request_id: Optional[str],
    ) -> Dict[str, Any]:
        diagnostics_coding: List[Dict[str, Any]] = (
            FhirBundleAppender.get_diagnostic_coding(
                access_token=access_token,
                url=url,
                resource_type=resource_type,
                id_=id_,
                status=status,
            )
        )
        return {
            "resourceType": "OperationOutcome",
            "issue": [
                {
                    "severity": "error",
                    "code": (
                        "expired"
                        if status == 401
                        else ("not-found" if status == 404 else "exception")
                    ),
                    "details": {"coding": diagnostics_coding},
                    "diagnostics": json.dumps(
                        {
                            "url": url,
                            "error": error,
                            "status": status,
                            "extra_context_to_return": extra_context_to_return,
                            "accessToken": access_token,
                            "requestId": request_id,
                            "resourceType": resource_type,
                            "id": id_,
                        }
                    ),
                }
            ],
        }

    @staticmethod
    def get_diagnostic_coding(
        *,
        url: Optional[str],
        resource_type: Optional[str],
        id_: Optional[str | List[str]],
        status: int,
        access_token: Optional[str],
    ) -> List[Dict[str, Any]]:
        diagnostics_coding_nullable: List[Optional[Dict[str, Any]]] = [
            (
                {
                    "system": "https://www.icanbwell.com/url",
                    "code": url,
                }
                if url
                else None
            ),
            (
                {
                    "system": "https://www.icanbwell.com/resourceType",
                    "code": resource_type,
                }
                if resource_type
                else None
            ),
            (
                {
                    "system": "https://www.icanbwell.com/id",
                    "code": (",".join(id_) if isinstance(id_, list) else id_),
                }
                if id_
                else None
            ),
            {
                "system": "https://www.icanbwell.com/statuscode",
                "code": status,
            },
            (
                {
                    "system": "https://www.icanbwell.com/accessToken",
                    "code": access_token,
                }
                if access_token
                else None
            ),
        ]
        diagnostics_coding: List[Dict[str, Any]] = [
            c for c in diagnostics_coding_nullable if c is not None
        ]
        return diagnostics_coding

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

    @staticmethod
    def sort_resources_in_list(
        *,
        resources: List[Dict[str, Any]],
        fn_sort: Callable[[Dict[str, Any]], str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Sorts the resources in the bundle

        :param resources: The resources to sort
        :param fn_sort: The function to use to sort the resources (Optional).  if not provided, the resources will be sorted by resourceType/id
        """
        if not resources:
            return resources

        if not fn_sort:
            fn_sort = lambda r: (
                (r.get("resourceType", "") + "/" + r.get("id", "")) if r else ""
            )
        resources = sorted(
            resources,
            key=fn_sort,
        )
        return resources
