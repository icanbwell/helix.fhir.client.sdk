import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from compressedfhir.fhir.fhir_bundle import FhirBundle
from compressedfhir.fhir.fhir_bundle_entry import FhirBundleEntry
from compressedfhir.fhir.fhir_bundle_entry_list import FhirBundleEntryList
from compressedfhir.fhir.fhir_bundle_entry_request import FhirBundleEntryRequest
from compressedfhir.fhir.fhir_bundle_entry_response import (
    FhirBundleEntryResponse,
)
from compressedfhir.fhir.fhir_resource import FhirResource
from compressedfhir.fhir.fhir_resource_list import FhirResourceList
from compressedfhir.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)

from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


class FhirBundleAppender:
    """
    This class appends responses to a bundle


    """

    @staticmethod
    def append_responses(
        *,
        responses: list[FhirGetResponse],
        bundle: FhirBundle,
        storage_mode: CompressedDictStorageMode,
    ) -> FhirBundle:
        """
        Appends responses to the bundle.  If there was an error then it appends OperationOutcome resources to the bundle


        :param responses: The responses to append
        :param bundle: The bundle to append to
        :param storage_mode: The storage mode to use for the bundle entries
        :return: The bundle with the responses appended
        """
        response: FhirGetResponse
        bundle_entries: FhirBundleEntryList = FhirBundleEntryList()
        for response in responses:
            bundle_entries_for_response: FhirBundleEntryList = FhirBundleAppender.add_operation_outcomes_to_response(
                response=response, storage_mode=storage_mode
            )
            bundle_entries.extend(bundle_entries_for_response)

        bundle.entry = bundle_entries
        return bundle

    @staticmethod
    def add_operation_outcomes_to_response(
        *, response: FhirGetResponse, storage_mode: CompressedDictStorageMode
    ) -> FhirBundleEntryList:
        bundle_entries: FhirBundleEntryList = response.get_bundle_entries()
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
            storage_mode=storage_mode,
        )

    @staticmethod
    def add_operation_outcomes_to_bundle_entries(
        *,
        bundle_entries: FhirBundleEntryList,
        error: str | None,
        url: str,
        resource_type: str | None,
        id_: str | list[str] | None,
        status: int,
        access_token: str | None,
        extra_context_to_return: dict[str, Any] | None,
        request_id: str | None,
        last_modified: datetime | None,
        etag: str | None,
        storage_mode: CompressedDictStorageMode,
    ) -> FhirBundleEntryList:
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
        :param storage_mode: The storage mode to use for the bundle entries
        """
        diagnostics_coding: list[dict[str, Any]] = FhirBundleAppender.get_diagnostic_coding(
            access_token=access_token,
            url=url,
            resource_type=resource_type,
            id_=id_,
            status=status,
        )

        bundle_entry: FhirBundleEntry
        for bundle_entry in bundle_entries:
            if bundle_entry.resource and bundle_entry.resource.resource_type == "OperationOutcome":
                # This is an OperationOutcome resource so we need to add the diagnostics to it
                bundle_entry.resource = FhirBundle.add_diagnostics_to_operation_outcomes(
                    resource=bundle_entry.resource,
                    diagnostics_coding=diagnostics_coding,
                )

        # now add a bundle entry for errors
        if error and len(bundle_entries) == 0:
            operation_outcome: FhirResource = FhirBundleAppender.create_operation_outcome_resource(
                error=error,
                url=url,
                resource_type=resource_type,
                id_=id_,
                status=status,
                access_token=access_token,
                extra_context_to_return=extra_context_to_return,
                request_id=request_id,
                storage_mode=storage_mode,
            )
            bundle_entries.append(
                FhirBundleEntry(
                    request=FhirBundleEntryRequest(url=url),
                    response=FhirBundleEntryResponse(
                        status=str(status),
                        lastModified=last_modified,
                        etag=etag,
                    ),
                    resource=operation_outcome,
                    storage_mode=storage_mode,
                )
            )
        return bundle_entries

    @staticmethod
    def create_operation_outcome_resource(
        *,
        error: str | None,
        url: str,
        resource_type: str | None,
        id_: str | list[str] | None,
        status: int,
        access_token: str | None,
        extra_context_to_return: dict[str, Any] | None,
        request_id: str | None,
        storage_mode: CompressedDictStorageMode,
    ) -> FhirResource:
        diagnostics_coding: list[dict[str, Any]] = FhirBundleAppender.get_diagnostic_coding(
            access_token=access_token,
            url=url,
            resource_type=resource_type,
            id_=id_,
            status=status,
        )
        return FhirResource(
            initial_dict={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": ("expired" if status == 401 else ("not-found" if status == 404 else "exception")),
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
            },
            storage_mode=storage_mode,
        )

    @staticmethod
    def get_diagnostic_coding(
        *,
        url: str | None,
        resource_type: str | None,
        id_: str | list[str] | None,
        status: int,
        access_token: str | None,
    ) -> list[dict[str, Any]]:
        diagnostics_coding_nullable: list[dict[str, Any] | None] = [
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
        diagnostics_coding: list[dict[str, Any]] = [c for c in diagnostics_coding_nullable if c is not None]
        return diagnostics_coding

    @staticmethod
    def remove_duplicate_resources(*, bundle: FhirBundle) -> FhirBundle:
        """
        Removes duplicate resources from the bundle

        :param bundle: The bundle to remove duplicates from
        :return: The bundle with duplicates removed
        """
        if not bundle.entry:
            return bundle
        bundle_entries: FhirBundleEntryList = bundle.entry
        unique_bundle_entries: FhirBundleEntryList = FhirBundleEntryList(
            {
                f"{e.resource['resourceType']}/{e.resource['id']}": e
                for e in bundle_entries
                if e.resource and e.resource.resource_type and e.resource.id
            }.values()
        )
        null_id_bundle_entries: FhirBundleEntryList = FhirBundleEntryList(
            [e for e in bundle_entries if not e.resource or not e.resource.resource_type]
        )
        unique_bundle_entries.extend(null_id_bundle_entries)
        bundle.entry = unique_bundle_entries

        return bundle

    @staticmethod
    def sort_resources(*, bundle: FhirBundle, fn_sort: Callable[[FhirBundleEntry], str] | None = None) -> FhirBundle:
        """
        Sorts the resources in the bundle

        :param bundle: The bundle to sort
        :param fn_sort: The function to use to sort the resources (Optional).  if not provided, the resources will be sorted by resourceType/id
        """
        if not bundle.entry:
            return bundle

        def my_sort(
            e: FhirBundleEntry,
        ) -> str:
            return (e.resource.get("resourceType", "") + "/" + e.resource.get("id", "")) if e.resource else ""

        if not fn_sort:
            fn_sort = my_sort
        bundle.entry = FhirBundleEntryList(
            sorted(
                bundle.entry,
                key=fn_sort,
            )
        )
        return bundle

    @staticmethod
    def sort_resources_in_list(
        *,
        resources: FhirResourceList,
        fn_sort: Callable[[FhirResource], str] | None = None,
    ) -> FhirResourceList:
        """
        Sorts the resources in the bundle

        :param resources: The resources to sort
        :param fn_sort: The function to use to sort the resources (Optional).  if not provided, the resources will be sorted by resourceType/id
        """
        if not resources:
            return resources

        def my_sort(
            r: FhirResource,
        ) -> str:
            return (r.get("resourceType", "") + "/" + r.get("id", "")) if r else ""

        if not fn_sort:
            fn_sort = my_sort

        return FhirResourceList(
            sorted(
                resources,
                key=fn_sort,
            )
        )
