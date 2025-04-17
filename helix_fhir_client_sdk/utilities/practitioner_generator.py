from typing import Any


class PractitionerGenerator:
    @staticmethod
    def generate_practitioner(*, practitioner_id: int) -> dict[str, Any]:
        return {
            "resourceType": "Practitioner",
            "id": f"practitioner-{practitioner_id}",
            "meta": {
                "source": "http://www.icanbwell.com",
                "security": [
                    {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                    {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
                ],
            },
            "name": [
                {
                    "family": f"Family{practitioner_id}",
                    "given": [f"Given{practitioner_id}"],
                }
            ],
        }

    @staticmethod
    def generate_organization(*, organization_id: int) -> dict[str, Any]:
        return {
            "resourceType": "Organization",
            "meta": {
                "source": "http://www.icanbwell.com",
                "security": [
                    {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                    {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
                ],
            },
            "id": f"organization-{organization_id}",
            "name": f"Organization{organization_id}",
        }

    @staticmethod
    def generate_practitioner_role(*, practitioner_id: int, organization_id: int, role_id: str) -> dict[str, Any]:
        return {
            "resourceType": "PractitionerRole",
            "id": f"role-{role_id}",
            "meta": {
                "source": "http://www.icanbwell.com",
                "security": [
                    {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                    {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
                ],
            },
            "practitioner": {"reference": f"Practitioner/practitioner-{practitioner_id}"},
            "organization": {"reference": f"Organization/organization-{organization_id}"},
            "code": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/practitioner-role",
                            "code": "doctor",
                            "display": "Doctor",
                        }
                    ]
                }
            ],
        }

    @staticmethod
    def generate_resources_bundle(*, count: int, roles_per_practitioner: int) -> dict[str, Any]:
        practitioners = []
        organizations = []
        practitioner_roles = []

        for i in range(0, count):
            practitioners.append(PractitionerGenerator.generate_practitioner(practitioner_id=i))
            organizations.append(PractitionerGenerator.generate_organization(organization_id=i))
            for j in range(1, roles_per_practitioner):
                practitioner_roles.append(
                    PractitionerGenerator.generate_practitioner_role(
                        practitioner_id=i, organization_id=i, role_id=f"{i}-{j}"
                    )
                )

        return {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [{"resource": r} for r in practitioners + organizations + practitioner_roles],
        }

    @staticmethod
    def get_ids(*, count: int, roles_per_practitioner: int) -> dict[str, list[str]]:
        return {
            "Practitioner": [f"practitioner-{i}" for i in range(0, count)],
            "Organization": [f"organization-{i}" for i in range(0, count)],
            "PractitionerRole": [f"role-{i}-{j}" for j in range(0, roles_per_practitioner) for i in range(1, count)],
        }
