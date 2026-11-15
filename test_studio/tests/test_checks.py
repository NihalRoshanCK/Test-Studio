"""Data check comparison; no site needed: env/bin/python -m unittest test_studio.tests.test_checks"""

import unittest

from test_studio import checks

COLS = [{"fieldname": "warehouse", "fieldtype": "Link"}, {"fieldname": "qty", "fieldtype": "Float"},
	{"fieldname": "value", "fieldtype": "Currency"}]


class TestDiff(unittest.TestCase):
	def test_added_removed_changed(self):
		before = [["Transit", 0, 154933.8], ["Yard", 4, 100.0], ["Old", 1, 5.0]]
		after = [["Transit", 0, 0.0], ["Yard", 4, 100.0], ["New", 2, 9.0]]
		d = checks.diff(COLS, before, after)
		self.assertEqual(d["added"], [["New", 2, 9.0]])
		self.assertEqual(d["removed"], [["Old", 1, 5.0]])
		self.assertEqual(d["changed"], [{"before": ["Transit", 0, 154933.8], "after": ["Transit", 0, 0.0]}])

	def test_duplicate_keys_kept(self):
		d = checks.diff(COLS, [["A", 1, 1.0]], [["A", 1, 1.0], ["A", 2, 2.0]])
		self.assertEqual((d["added"], d["changed"]), ([["A", 2, 2.0]], []))

	def test_query_report_column_strings(self):
		self.assertEqual(checks._column("Value Before:Currency:120"),
			{"label": "Value Before", "fieldname": "value_before", "fieldtype": "Currency"})
		self.assertEqual(checks._column("Voucher Type::110")["fieldtype"], "Data")


if __name__ == "__main__":
	unittest.main()
