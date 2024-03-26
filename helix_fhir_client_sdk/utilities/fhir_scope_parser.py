import logging
from typing import Optional, List

from helix_fhir_client_sdk.utilities.fhir_scope_parser_result import (
    FhirScopeParserResult,
)


class FhirScopeParser:
    def __init__(self, scopes: Optional[List[str]]) -> None:
        """
        This class parses SMART on FHIR scopes and can answer whether a resource is allowed to be downloaded
        https://build.fhir.org/ig/HL7/smart-app-launch/scopes-and-launch-context.html

        :param scopes: The scopes to parse.
        """
        self.logger = logging.getLogger(__name__)
        self.scopes: Optional[List[str]] = scopes
        self.parsed_scopes: Optional[List[FhirScopeParserResult]] = (
            self.parse_scopes(" ".join([s for s in scopes if s]))
            if scopes and len([s for s in scopes if s])
            else None
        )

    @staticmethod
    def _get_patient_demographic_read_scopes() -> List[FhirScopeParserResult]:
        """
        Returns a list of scopes as FhirScopeParserResult objects that allow patient demographics to be read

        :return: A list of FhirScopeParserResult objects that allow patient demographics to be read
        """
        patient_patient_read = FhirScopeParserResult(resource_type="patient", operation="Patient", interaction="read")
        patient_star_read = FhirScopeParserResult(resource_type="Patient", operation="*", interaction="read")
        user_patient_read = FhirScopeParserResult(resource_type="user", operation="Patient", interaction="read")
        user_star_read = FhirScopeParserResult(resource_type="user", operation="*", interaction="read")

        return [patient_patient_read, patient_star_read, user_patient_read, user_star_read]

    def parse_scopes(self, scopes: Optional[str]) -> List[FhirScopeParserResult]:
        """
        Parses the given scopes into a list of FhirScopeParserResult objects.

        :param scopes: The scopes to parse.
        :return: A list of FhirScopeParserResult objects.
        """
        if not scopes:
            return []
        parsed_scopes: List[FhirScopeParserResult] = []
        scope_list = scopes.split(" ")

        for scope in scope_list:
            if "/" in scope:
                resource, interaction = scope.split("/")
                if "." in interaction:
                    operation, permission = interaction.split(".")
                    parsed_scopes.append(
                        FhirScopeParserResult(
                            resource_type=resource.strip(" \n") if resource else None,
                            operation=operation.strip(" \n") if operation else None,
                            interaction=permission.strip(" \n").lower()
                            if permission
                            else None,
                        )
                    )
                else:
                    parsed_scopes.append(
                        FhirScopeParserResult(
                            resource_type=resource.strip(" \n") if resource else None,
                            interaction=interaction.strip(" \n").lower()
                            if interaction
                            else None,
                        )
                    )
            elif scope and scope.strip(" \n") != "":
                parsed_scopes.append(
                    FhirScopeParserResult(
                        scope=scope,
                    )
                )

        # log warning in event that parsed_scopes does not include a scope that allows patient demographics to be read
        if not any([demographic_scope in parsed_scopes for demographic_scope in
                    self._get_patient_demographic_read_scopes()]):
            self.logger.warning(f"Missing patient demographic read scopes in: {scope_list}")

        return parsed_scopes

    def scope_allows(self, resource_type: str, interaction: str = "read") -> bool:
        """
        Returns whether the scope allows the given resource type and interaction.


        :param resource_type: The resource type to check.
        :param interaction: The interaction to check.
        :return: True if the scope allows the given resource type and interaction, False otherwise.
        """
        # if there are no scopes then allow everything
        if not self.parsed_scopes:
            return True

        # check if this is a valid SMART on FHIR scope
        if not any([s for s in self.parsed_scopes if s.resource_type == "patient"]):
            return True

        # These resources are always allowed
        if resource_type in ["OperationOutcome", "Bundle"]:
            return True

        assert resource_type
        assert interaction

        # note that resource_type is actually called Operation in SMART on FHIR scopes:
        # A SMART on FHIR scope string is constructed as resourceType.operation.permission.
        # For example, the scope string patient/*.read requests read-only access to all patient-related resources.
        scope: FhirScopeParserResult
        for scope in self.parsed_scopes:
            if (
                scope.operation
                and scope.interaction
                and (
                    scope.operation == "*"
                    or scope.operation.lower() == resource_type.lower()
                )
                and (
                    scope.interaction == "*"
                    or scope.interaction.lower() == interaction.lower()
                )
            ):
                return True
        return False
