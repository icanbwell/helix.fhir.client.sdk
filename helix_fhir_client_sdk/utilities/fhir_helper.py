import copy
import logging
from logging import Logger
from typing import Any

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.utilities.list_chunker import ListChunker


class FhirHelper:
    @staticmethod
    async def create_test_patients(count: int) -> dict[str, Any]:
        logger: Logger = logging.getLogger("fhir-client")
        # now create 1000 patients
        patient = {
            "resourceType": "Patient",
            "id": "example",
            "meta": {
                "source": "http://www.icanbwell.com",
                "security": [
                    {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                    {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
                ],
            },
            "text": {
                "status": "generated",
                "div": '<div xmlns="http://www.w3.org/1999/xhtml">John Doe</div>',
            },
            "identifier": [
                {
                    "use": "usual",
                    "type": {"coding": [{"system": "http://hl7.org/fhir/v2/0203", "code": "MR"}]},
                    "system": "http://example.com",
                    "value": "12345",
                }
            ],
            "active": True,
            "name": [{"use": "official", "family": "Doe", "given": ["John"]}],
            "gender": "male",
            "birthDate": "1990-01-01",
            "address": [
                {
                    "use": "home",
                    "line": ["123 Main St"],
                    "city": "Anytown",
                    "state": "CA",
                    "postalCode": "12345",
                    "country": "USA",
                }
            ],
        }
        # add 1000 patients
        logger.info(f"Adding {count} patients")
        patients: list[dict[str, Any]] = []
        for i in range(count):
            patient_new = copy.deepcopy(patient)
            patient_new["id"] = f"example-{i}"
            patient_new["identifier"][0]["value"] = f"12345-{i}"  # type: ignore[index]
            patient_new["name"][0]["family"] = f"Doe-{i}"  # type: ignore[index]
            patient_new["name"][0]["given"][0] = f"John-{i}"  # type: ignore[index]
            patient_new["address"][0]["line"][0] = f"123 Main St-{i}"  # type: ignore[index]
            patient_new["address"][0]["city"] = f"Anytown-{i}"  # type: ignore[index]
            patient_new["address"][0]["state"] = f"CA-{i}"  # type: ignore[index]
            patient_new["address"][0]["postalCode"] = f"12345-{i}"  # type: ignore[index]
            patient_new["address"][0]["country"] = f"USA-{i}"  # type: ignore[index]
            patients.append(patient_new)
        logger.info(f"Added {count} patients")
        bundle = {
            "resourceType": "Bundle",
            "id": "12355",
            "meta": {
                "source": "http://www.icanbwell.com",
                "security": [
                    {"system": "https://www.icanbwell.com/access", "code": "bwell"},
                    {"system": "https://www.icanbwell.com/owner", "code": "bwell"},
                ],
            },
            "entry": [{"resource": p} for p in patients],
        }
        return bundle

    @staticmethod
    async def delete_resources_by_ids_async(fhir_client: FhirClient, resource_type: str, id_list: list[str]) -> None:
        logger: Logger = logging.getLogger("FhirHelper.delete_resources_by_ids_async")
        count: int = len(id_list)
        logger.info(f"Deleting {count} {resource_type} resources: {id_list}")
        for chunk_resource_ids in ListChunker.divide_into_chunks(id_list, 100):
            fhir_client = fhir_client.resource(resource_type)
            delete_response = await fhir_client.id_(chunk_resource_ids).delete_async()
            assert delete_response.status == 204, delete_response.responses
            logger.info(f"Deleted {len(chunk_resource_ids)} {resource_type} resources")
        logger.info(f"Finished deleting {count} {resource_type} resources")
