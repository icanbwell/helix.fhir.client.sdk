import json

import requests_mock

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse


def test_fhir_client_bundle() -> None:
    with requests_mock.Mocker() as mock:
        url = "http://foo"
        response_text = {
            "resourceType": "Bundle",
            "id": "1437321965",
            "entry": [
                {
                    "link": "https://localhost:3000/4_0_0/Practitioner/1437321965",
                    "resource": {
                        "resourceType": "Practitioner",
                        "id": "1437321965",
                        "meta": {
                            "versionId": "1",
                            "lastUpdated": "2021-01-13T04:37:06+00:00",
                            "source": "http://medstarhealth.org/provider",
                        },
                        "identifier": [
                            {
                                "use": "usual",
                                "type": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                            "code": "PRN",
                                        }
                                    ]
                                },
                                "system": "http://medstarhealth.org",
                                "value": "500524",
                            },
                            {
                                "use": "official",
                                "type": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                            "code": "NPI",
                                        }
                                    ]
                                },
                                "system": "http://hl7.org/fhir/sid/us-npi",
                                "value": "1437321965",
                            },
                        ],
                        "active": True,
                        "name": [
                            {
                                "use": "usual",
                                "text": "ZOOVIA AMAN MD",
                                "family": "AMAN",
                                "given": ["ZOOVIA", ""],
                            }
                        ],
                        "gender": "female",
                        "qualification": [
                            {
                                "code": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/ValueSet/v2-2.7-030",
                                            "code": "MD",
                                        }
                                    ]
                                }
                            },
                            {
                                "code": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/ValueSet/v2-2.7-030",
                                            "code": "MD",
                                        }
                                    ]
                                },
                                "period": {"start": "2011-01-01", "end": "2023-12-31"},
                                "issuer": {
                                    "reference": "Organization/Harpers_Ferry_Family_Medicine"
                                },
                            },
                        ],
                        "communication": [
                            {"coding": [{"system": "urn:ietf:bcp:47", "code": "en"}]}
                        ],
                    },
                },
                {
                    "link": "https://localhost:3000/4_0_0/PractitionerRole/1437321965-ML1-MLSW",
                    "resource": {
                        "resourceType": "PractitionerRole",
                        "id": "1437321965-ML1-MLSW",
                        "meta": {
                            "versionId": "1",
                            "lastUpdated": "2021-01-13T04:37:24+00:00",
                            "source": "http://medstarhealth.org/provider",
                        },
                        "practitioner": {"reference": "Practitioner/1437321965"},
                        "organization": {"reference": "Organization/Medstar-15888213"},
                        "code": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/practitioner-role",
                                        "code": "doctor",
                                        "display": "Doctor",
                                    }
                                ],
                                "text": "Doctor",
                            }
                        ],
                        "specialty": [
                            {
                                "coding": [
                                    {
                                        "system": "https://www.http://medstarhealth.org",
                                        "code": "Family Medicine",
                                        "display": "Family Medicine",
                                    }
                                ],
                                "text": "Family Medicine",
                            },
                            {
                                "coding": [
                                    {
                                        "system": "http://nucc.org/provider-taxonomy",
                                        "code": "207Q00000X",
                                        "display": "Family Medicine",
                                    }
                                ],
                                "text": "Family Medicine",
                            },
                            {
                                "coding": [
                                    {
                                        "system": "http://nucc.org/provider-taxonomy",
                                        "code": "261QP2300X",
                                        "display": "Primary Care",
                                    }
                                ],
                                "text": "Primary Care",
                            },
                        ],
                        "location": [{"reference": "Location/Medstar-Alias-ML1-MLSW"}],
                    },
                },
            ],
        }
        expected_response = {
            "practitioner": [
                {
                    "resourceType": "Practitioner",
                    "id": "1437321965",
                    "meta": {
                        "versionId": "1",
                        "lastUpdated": "2021-01-13T04:37:06+00:00",
                        "source": "http://medstarhealth.org/provider",
                    },
                    "identifier": [
                        {
                            "use": "usual",
                            "type": {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                        "code": "PRN",
                                    }
                                ]
                            },
                            "system": "http://medstarhealth.org",
                            "value": "500524",
                        },
                        {
                            "use": "official",
                            "type": {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                        "code": "NPI",
                                    }
                                ]
                            },
                            "system": "http://hl7.org/fhir/sid/us-npi",
                            "value": "1437321965",
                        },
                    ],
                    "active": True,
                    "name": [
                        {
                            "use": "usual",
                            "text": "ZOOVIA AMAN MD",
                            "family": "AMAN",
                            "given": ["ZOOVIA", ""],
                        }
                    ],
                    "gender": "female",
                    "qualification": [
                        {
                            "code": {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/ValueSet/v2-2.7-030",
                                        "code": "MD",
                                    }
                                ]
                            }
                        },
                        {
                            "code": {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/ValueSet/v2-2.7-030",
                                        "code": "MD",
                                    }
                                ]
                            },
                            "period": {"start": "2011-01-01", "end": "2023-12-31"},
                            "issuer": {
                                "reference": "Organization/Harpers_Ferry_Family_Medicine"
                            },
                        },
                    ],
                    "communication": [
                        {"coding": [{"system": "urn:ietf:bcp:47", "code": "en"}]}
                    ],
                }
            ],
            "practitionerrole": [
                {
                    "resourceType": "PractitionerRole",
                    "id": "1437321965-ML1-MLSW",
                    "meta": {
                        "versionId": "1",
                        "lastUpdated": "2021-01-13T04:37:24+00:00",
                        "source": "http://medstarhealth.org/provider",
                    },
                    "practitioner": {"reference": "Practitioner/1437321965"},
                    "organization": {"reference": "Organization/Medstar-15888213"},
                    "code": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/practitioner-role",
                                    "code": "doctor",
                                    "display": "Doctor",
                                }
                            ],
                            "text": "Doctor",
                        }
                    ],
                    "specialty": [
                        {
                            "coding": [
                                {
                                    "system": "https://www.http://medstarhealth.org",
                                    "code": "Family Medicine",
                                    "display": "Family Medicine",
                                }
                            ],
                            "text": "Family Medicine",
                        },
                        {
                            "coding": [
                                {
                                    "system": "http://nucc.org/provider-taxonomy",
                                    "code": "207Q00000X",
                                    "display": "Family Medicine",
                                }
                            ],
                            "text": "Family Medicine",
                        },
                        {
                            "coding": [
                                {
                                    "system": "http://nucc.org/provider-taxonomy",
                                    "code": "261QP2300X",
                                    "display": "Primary Care",
                                }
                            ],
                            "text": "Primary Care",
                        },
                    ],
                    "location": [{"reference": "Location/Medstar-Alias-ML1-MLSW"}],
                }
            ],
        }
        mock.get(f"{url}/Patient", json=response_text)

        fhir_client = FhirClient().separate_bundle_resources(True)
        fhir_client = fhir_client.url(url).resource("Patient")
        response: FhirGetResponse = fhir_client.get()

        print(response.responses)
        assert response.responses == [json.dumps(expected_response)]
