from typing import Optional, List

from helix_fhir_client_sdk.utilities.fhir_scope_parser_result import (
    FhirScopeParserResult,
)


class FhirScopeParser:
    @staticmethod
    def parse_scopes(scopes: Optional[str]) -> List[FhirScopeParserResult]:
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

        return parsed_scopes
