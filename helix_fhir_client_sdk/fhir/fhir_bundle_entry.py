import json
from typing import Any, Dict, Optional

from helix_fhir_client_sdk.fhir.fhir_bundle_entry_request import FhirBundleEntryRequest
from helix_fhir_client_sdk.fhir.fhir_bundle_entry_response import (
    FhirBundleEntryResponse,
)
from helix_fhir_client_sdk.fhir.fhir_resource import FhirResource
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict import (
    CompressedDict,
)
from helix_fhir_client_sdk.utilities.compressed_dict.v1.compressed_dict_storage_mode import (
    CompressedDictStorageMode,
)
from helix_fhir_client_sdk.utilities.fhir_json_encoder import FhirJSONEncoder


class FhirBundleEntry:
    __slots__ = ["_resource", "request", "response", "fullUrl", "storage_mode"]

    # noinspection PyPep8Naming
    def __init__(
        self,
        *,
        fullUrl: Optional[str] = None,
        resource: Dict[str, Any] | FhirResource | None,
        request: Optional[FhirBundleEntryRequest],
        response: Optional[FhirBundleEntryResponse],
        storage_mode: CompressedDictStorageMode,
    ) -> None:
        """
        Initializes a BundleEntry object.

        :param fullUrl: The full URL of the entry.
        :param resource: The FHIR resource associated with the entry.
        :param request: The request information associated with the entry.
        :param response: The response information associated with the entry.
        :param storage_mode: The storage mode for the resource.
        """
        self._resource: Optional[FhirResource] = (
            resource
            if isinstance(resource, CompressedDict)
            else (
                FhirResource(initial_dict=resource, storage_mode=storage_mode)
                if resource is not None
                else None
            )
        )
        self.request: Optional[FhirBundleEntryRequest] = request
        self.response: Optional[FhirBundleEntryResponse] = response
        self.fullUrl: Optional[str] = fullUrl
        self.storage_mode: CompressedDictStorageMode = storage_mode

    @property
    def resource(self) -> Optional[FhirResource]:
        """
        Returns the FHIR resource associated with the entry.

        :return: The FHIR resource.
        """
        return self._resource

    @resource.setter
    def resource(self, value: Dict[str, Any] | FhirResource | None) -> None:
        """
        Sets the FHIR resource associated with the entry.

        :param value: The FHIR resource to set.
        """
        if value is not None:
            if isinstance(value, CompressedDict):
                self._resource = value
            else:
                if self._resource is None:
                    self._resource = FhirResource(
                        initial_dict=value, storage_mode=self.storage_mode
                    )
                else:
                    self._resource.replace(value=value)
        else:
            self._resource = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if self.fullUrl is not None:
            result["fullUrl"] = self.fullUrl
        if self.resource is not None:
            result["resource"] = self.resource.to_dict()
        if self.request is not None:
            result["request"] = self.request.to_dict()
        if self.response is not None:
            result["response"] = self.response.to_dict()
        return result

    @staticmethod
    def from_dict(
        d: Dict[str, Any], storage_mode: CompressedDictStorageMode
    ) -> "FhirBundleEntry":
        return FhirBundleEntry(
            fullUrl=d["fullUrl"] if "fullUrl" in d else None,
            resource=(
                FhirResource(initial_dict=d["resource"], storage_mode=storage_mode)
                if "resource" in d
                else None
            ),
            request=(
                FhirBundleEntryRequest.from_dict(d["request"])
                if "request" in d
                else None
            ),
            response=(
                FhirBundleEntryResponse.from_dict(d["response"])
                if "response" in d
                else None
            ),
            storage_mode=storage_mode,
        )

    def __repr__(self) -> str:
        """
        Returns a string representation of the BundleEntry object.

        :return: A string representation of the BundleEntry.
        """
        return f"resource={self.resource}"

    def to_json(self) -> str:
        """
        Converts the BundleEntry object to a JSON string.

        :return: A JSON string representation of the BundleEntry.
        """
        return json.dumps(obj=self.to_dict(), cls=FhirJSONEncoder)

    def copy(self) -> "FhirBundleEntry":
        """
        Creates a copy of the BundleEntry object.

        :return: A new BundleEntry object with the same attributes.
        """
        return FhirBundleEntry(
            fullUrl=self.fullUrl,
            resource=self.resource.copy() if self.resource else None,
            request=self.request.copy() if self.request else None,
            response=self.response.copy() if self.response else None,
            storage_mode=self.storage_mode,
        )
