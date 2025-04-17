import unittest
from helix_fhir_client_sdk.filters.base_filter import BaseFilter


class TestBaseFilter(unittest.TestCase):
    def test_base_filter_str(self):
        base_filter = BaseFilter()
        with self.assertRaises(NotImplementedError):
            str(base_filter)

    def test_base_filter_init(self):
        base_filter = BaseFilter()
        self.assertIsInstance(base_filter, BaseFilter)


if __name__ == "__main__":
    unittest.main()
