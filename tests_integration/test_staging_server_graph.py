from logging import Logger

import pytest

from helix_fhir_client_sdk.fhir_client import FhirClient
from helix_fhir_client_sdk.responses.fhir_get_response import FhirGetResponse
from tests.logger_for_test import LoggerForTest


@pytest.mark.skip("for testing")
async def test_staging_server_graph() -> None:
    logger: Logger = LoggerForTest()
    url = "https://fhir.staging.bwell.zone/4_0_0"
    fhir_client = FhirClient()
    fhir_client = fhir_client.url(url).resource("Practitioner")
    fhir_client = fhir_client.action("$graph")
    fhir_client = fhir_client.action_payload(
        {
            "resourceType": "GraphDefinition",
            "id": "o",
            "name": "provider_everything",
            "status": "active",
            "start": "Practitioner",
            "link": [
                {
                    "description": "Practitioner Roles for this Practitioner",
                    "target": [
                        {
                            "type": "PractitionerRole",
                            "params": "practitioner={ref}&active:not=false&_security=https://www.icanbwell.com/access|healthgrades",
                            "link": [
                                {
                                    "path": "organization",
                                    "target": [{"type": "Organization"}],
                                },
                                {
                                    "path": "location[x]",
                                    "target": [{"type": "Location"}],
                                },
                                {
                                    "path": "healthcareService[x]",
                                    "target": [{"type": "HealthcareService"}],
                                },
                                {
                                    "path": "extension.extension:url=plan",
                                    "target": [
                                        {
                                            "link": [
                                                {
                                                    "path": "valueReference",
                                                    "target": [{"type": "InsurancePlan"}],
                                                }
                                            ]
                                        }
                                    ],
                                },
                                {
                                    "target": [
                                        {
                                            "type": "Schedule",
                                            "params": "actor={ref}&_security=https://www.icanbwell.com/access|healthgrades",
                                        }
                                    ]
                                },
                            ],
                        }
                    ],
                },
                {
                    "description": "Group",
                    "target": [
                        {
                            "type": "Group",
                            "params": "member={ref}&_security=https://www.icanbwell.com/access|healthgrades",
                        }
                    ],
                },
                {
                    "description": "Review score for the practitioner",
                    "target": [
                        {
                            "type": "MeasureReport",
                            "params": "subject={ref}&_security=https://www.icanbwell.com/access|healthgrades",
                        }
                    ],
                },
            ],
        }
    )
    fhir_client = fhir_client.id_(
        [
            "1215560115",
            "1093339541",
            "1356737209",
            "1306849443",
            "1700195567",
            "1942720727",
            "1558624908",
            "1629294145",
            "1255621710",
            "1043686538",
            "1982788030",
            "1609307958",
            # "1063574812",
            # "1881620722",
            # "1275707556",
            # "1528511870",
            # "1497705008",
            # "1457956732",
            # "1467847715",
            # "1245784073",
            # "1649693326",
            # "1861917098",
            # "1902928369",
            # "1124089420",
            # "1205483831",
            # "1972006831",
            # "1629362132",
            # "1366785958",
            # "1609325570",
            # "1689193013",
            # "1407055528",
            # "1376747733",
            # "1962587576",
            # "1144656851",
            # "1851303630",
            # "1114074135",
            # "1760419519",
            # "1407808330",
            # "1841548336",
            # "1538570338",
            # "1780866756",
            # "1093741324",
            # "1821622663",
            # "1831326719",
            # "1649477175",
            # "1487610861",
            # "1679574453",
            # "1942425590",
            # "1932280989",
            # "1043619042",
            # "1437755170",
            # "1356325179",
            # "1609320555",
            # "1376984229",
            # "1396464434",
            # "1457658304",
            # "1396104725",
            # "1922242445",
            # "1548492853",
            # "1588139448",
            # "1386664423",
            # "1720140536",
            # "1003279753",
            # "1861015737",
            # "1336312537",
            # "1487626909",
            # "1437181013",
            # "1457896581",
            # "1225292469",
            # "1528090990",
            # "1376551721",
            # "1063917748",
            # "1386600666",
            # "1891787016",
            # "1457439689",
            # "1316089154",
            # "1962475434",
            # "1306032818",
            # "1811197742",
            # "1528430055",
            # "1033190988",
            # "1578707709",
            # "1003259649",
            # "1588063390",
            # "1245226877",
            # "1356640726",
            # "1275662124",
            # "1285173799",
            # "1437195245",
            # "1417434044",
            # "1700089414",
            # "1063430387",
            # "1174951453",
            # "1285781773",
            # "1407865181",
            # "1366852550",
            # "1851373641",
            # "1295027365",
            # "1356306468",
            # "1922591221"
        ]
    )
    fhir_client = fhir_client.additional_parameters(["contained=true"])
    fhir_client = fhir_client.auth_server_url("https://staging-icanbwell.auth.us-east-1.amazoncognito.com/oauth2/token")
    fhir_client = fhir_client.auth_scopes(["user/*.read", "user/*.write", "access/*.*"])
    fhir_client = fhir_client.login_token("")
    fhir_client = fhir_client.client_credentials(client_id="", client_secret="")
    fhir_client.set_access_token("")
    response: FhirGetResponse = await fhir_client.get_async()
    logger.info(response)
