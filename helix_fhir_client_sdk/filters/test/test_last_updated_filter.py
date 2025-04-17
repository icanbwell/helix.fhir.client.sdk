import unittest
from datetime import datetime
from helix_fhir_client_sdk.filters.last_updated_filter import LastUpdatedFilter


class TestLastUpdatedFilter(unittest.TestCase):
    def test_last_updated_filter_initialization(self):
        less_than = datetime(2023, 9, 1)
        greater_than = datetime(2023, 8, 1)
        last_updated_filter = LastUpdatedFilter(less_than=less_than, greater_than=greater_than)
        self.assertEqual(last_updated_filter.less_than, less_than)
        self.assertEqual(last_updated_filter.greater_than, greater_than)

    def test_last_updated_filter_str(self):
        less_than = datetime(2023, 9, 1)
        greater_than = datetime(2023, 8, 1)
        last_updated_filter = LastUpdatedFilter(less_than=less_than, greater_than=greater_than)
        self.assertEqual(str(last_updated_filter), "_lastUpdated=lt2023-09-01&_lastUpdated=gt2023-08-01")

    def test_last_updated_filter_str_only_less_than(self):
        less_than = datetime(2023, 9, 1)
        last_updated_filter = LastUpdatedFilter(less_than=less_than, greater_than=None)
        self.assertEqual(str(last_updated_filter), "_lastUpdated=lt2023-09-01")

    def test_last_updated_filter_str_only_greater_than(self):
        greater_than = datetime(2023, 8, 1)
        last_updated_filter = LastUpdatedFilter(less_than=None, greater_than=greater_than)
        self.assertEqual(str(last_updated_filter), "_lastUpdated=gt2023-08-01")

    def test_last_updated_filter_str_empty(self):
        last_updated_filter = LastUpdatedFilter(less_than=None, greater_than=None)
        self.assertEqual(str(last_updated_filter), "")

    def test_last_updated_filter_init_none(self):
        last_updated_filter = LastUpdatedFilter(less_than=None, greater_than=None)
        self.assertIsNone(last_updated_filter.less_than)
        self.assertIsNone(last_updated_filter.greater_than)


if __name__ == "__main__":
    unittest.main()
