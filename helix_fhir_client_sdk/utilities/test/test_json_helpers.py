from typing import Any

from compressedfhir.utilities.json_helpers import FhirClientJsonHelpers


class TestFhirClientJsonHelpers:
    def test_remove_none_values_from_dict_single_level(self) -> None:
        # Test removing None values from a simple dictionary
        input_dict = {"name": "John", "age": 30, "email": None, "phone": None}
        expected_output = {"name": "John", "age": 30}

        result = FhirClientJsonHelpers.remove_empty_elements(input_dict)
        assert result == expected_output

    def test_remove_none_values_from_dict_nested(self) -> None:
        # Test removing None values from a nested dictionary
        input_dict = {
            "patient": {
                "name": "Jane",
                "contact": None,
                "address": {"street": "123 Main St", "city": None},
            },
            "test_results": None,
        }
        expected_output = {"patient": {"name": "Jane", "address": {"street": "123 Main St"}}}

        result = FhirClientJsonHelpers.remove_empty_elements(input_dict)
        assert result == expected_output

    def test_remove_none_values_from_dict_or_list_with_list(self) -> None:
        # Test removing None values from a list of dictionaries
        input_list: list[dict[str, Any]] = [
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": None},
            {"name": None, "city": "New York"},
        ]
        expected_output = [
            {"name": "Alice", "age": 25},
            {"name": "Bob"},
            {"city": "New York"},
        ]

        result = FhirClientJsonHelpers.remove_empty_elements(input_list)
        assert result == expected_output

    def test_remove_none_values_from_dict_or_list_with_nested_complex_structure(
        self,
    ) -> None:
        # Test with a more complex nested structure
        input_dict = {
            "users": [
                {
                    "id": 1,
                    "name": "John",
                    "details": {"email": None, "phone": "123-456-7890"},
                    "links": [
                        {"url": "http://example.com", "active": None},
                        {"url": None, "active": True},
                        None,
                    ],
                },
                {"id": 2, "name": None, "details": None},
            ],
            "metadata": None,
        }

        expected_output = {
            "users": [
                {
                    "id": 1,
                    "name": "John",
                    "details": {"phone": "123-456-7890"},
                    "links": [
                        {"url": "http://example.com"},
                        {"active": True},
                    ],
                },
                {
                    "id": 2,
                },
            ],
        }

        result = FhirClientJsonHelpers.remove_empty_elements(input_dict)
        assert result == expected_output

    def test_remove_empty_values_from_dict_or_list_with_nested_complex_structure(
        self,
    ) -> None:
        # Test with a more complex nested structure
        input_dict = {
            "users": [
                {
                    "id": 1,
                    "name": "John",
                    "details": {"email": None, "phone": "123-456-7890"},
                    "links": [
                        {"url": "http://example.com", "active": None},
                        {"url": {}, "active": True},
                        None,
                    ],
                },
                {},
                {"id": 2, "name": None, "details": None},
            ],
            "metadata": None,
        }

        expected_output = {
            "users": [
                {
                    "id": 1,
                    "name": "John",
                    "details": {"phone": "123-456-7890"},
                    "links": [
                        {"url": "http://example.com"},
                        {"active": True},
                    ],
                },
                {
                    "id": 2,
                },
            ],
        }

        result = FhirClientJsonHelpers.remove_empty_elements(input_dict)
        assert result == expected_output

    def test_remove_empty_string_value(
        self,
    ) -> None:
        # Test with a more complex nested structure
        input_dict = {
            "resourceType": "Practitioner",
            "id": "ez8G1fAosfeD9EEA6iXlFQw3",
            "identifier": [
                {
                    "use": "usual",
                    "system": "urn:oid:1.2.840.114350.1.13.460.2.7.5.737384.228",
                    "value": "1111111111",
                },
                {
                    "use": "usual",
                    "type": {"text": "SERID"},
                    "system": "urn:oid:1.2.840.114350.1.13.460.2.7.5.737384.243",
                    "value": "222222",
                },
                {
                    "use": "usual",
                    "type": {"text": "INTERNAL"},
                    "system": "urn:oid:1.2.840.114350.1.13.460.2.7.2.836982",
                    "value": "   222222",
                },
                {
                    "use": "usual",
                    "type": {"text": "EXTERNAL"},
                    "system": "urn:oid:1.2.840.114350.1.13.460.2.7.2.836982",
                    "value": "222222",
                },
            ],
            "active": True,
            "name": [{"use": "usual", "text": " Unknown", "family": "Unknown", "given": [""]}],
            "meta": {
                "source": "https://interconnect.test.org/interconnect-prd-fhir/api/FHIR/R4//Practitioner/ez8G1fAosfeD9EEA6iXlFQw3",
                "security": [
                    {
                        "system": "https://www.icanbwell.com/owner",
                        "code": "test_health",
                    },
                    {
                        "system": "https://www.icanbwell.com/access",
                        "code": "test_health",
                    },
                    {
                        "system": "https://www.icanbwell.com/vendor",
                        "code": "test_health",
                    },
                    {
                        "system": "https://www.icanbwell.com/connectionType",
                        "code": "proa",
                    },
                ],
            },
        }

        expected_output = {
            "resourceType": "Practitioner",
            "id": "ez8G1fAosfeD9EEA6iXlFQw3",
            "identifier": [
                {
                    "use": "usual",
                    "system": "urn:oid:1.2.840.114350.1.13.460.2.7.5.737384.228",
                    "value": "1111111111",
                },
                {
                    "use": "usual",
                    "type": {"text": "SERID"},
                    "system": "urn:oid:1.2.840.114350.1.13.460.2.7.5.737384.243",
                    "value": "222222",
                },
                {
                    "use": "usual",
                    "type": {"text": "INTERNAL"},
                    "system": "urn:oid:1.2.840.114350.1.13.460.2.7.2.836982",
                    "value": "   222222",
                },
                {
                    "use": "usual",
                    "type": {"text": "EXTERNAL"},
                    "system": "urn:oid:1.2.840.114350.1.13.460.2.7.2.836982",
                    "value": "222222",
                },
            ],
            "active": True,
            "name": [
                {
                    "use": "usual",
                    "text": " Unknown",
                    "family": "Unknown",
                }
            ],
            "meta": {
                "source": "https://interconnect.test.org/interconnect-prd-fhir/api/FHIR/R4//Practitioner/ez8G1fAosfeD9EEA6iXlFQw3",
                "security": [
                    {
                        "system": "https://www.icanbwell.com/owner",
                        "code": "test_health",
                    },
                    {
                        "system": "https://www.icanbwell.com/access",
                        "code": "test_health",
                    },
                    {
                        "system": "https://www.icanbwell.com/vendor",
                        "code": "test_health",
                    },
                    {
                        "system": "https://www.icanbwell.com/connectionType",
                        "code": "proa",
                    },
                ],
            },
        }

        result = FhirClientJsonHelpers.remove_empty_elements(input_dict)
        assert result == expected_output
