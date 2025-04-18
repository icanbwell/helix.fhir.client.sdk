import unittest
from helix_fhir_client_sdk.filters.identifier_filter import IdentifierFilter


class TestIdentifierFilter(unittest.TestCase):
    def test_identifier_filter_initialization(self):
        system = "http://hl7.org/fhir/sid/us-npi"
        value = "1487831681"
        identifier_filter = IdentifierFilter(system=system, value=value)
        self.assertEqual(identifier_filter.system, system)
        self.assertEqual(identifier_filter.value, value)

    def test_identifier_filter_str(self):
        system = "http://hl7.org/fhir/sid/us-npi"
        value = "1487831681"
        identifier_filter = IdentifierFilter(system=system, value=value)
        self.assertEqual(str(identifier_filter), f"identifier={system}|{value}")


if __name__ == "__main__":
    unittest.main()
