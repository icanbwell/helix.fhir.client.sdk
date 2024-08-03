import copy
from typing import List, Dict, Any


class FhirHelper:
    @staticmethod
    async def create_test_patients(count: int) -> Dict[str, Any]:
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
                    "type": {
                        "coding": [
                            {"system": "http://hl7.org/fhir/v2/0203", "code": "MR"}
                        ]
                    },
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
        print(f"Adding {count} patients")
        patients: List[Dict[str, Any]] = []
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
        print(f"Added {count} patients")
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
