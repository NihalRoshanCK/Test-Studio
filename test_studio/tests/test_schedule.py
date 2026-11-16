"""When a scheduled suite is due; no site needed."""

import unittest
from datetime import datetime

from test_studio.runner import is_due

MON_2AM = datetime(2026, 11, 16, 2, 5)  # a Monday


class TestSchedule(unittest.TestCase):
	def test_hourly(self):
		self.assertTrue(is_due("Hourly", None, None, None, MON_2AM))
		self.assertFalse(is_due("Hourly", None, None, datetime(2026, 11, 16, 1, 30), MON_2AM))
		self.assertTrue(is_due("Hourly", None, None, datetime(2026, 11, 16, 1, 5), MON_2AM))

	def test_daily_once_at_its_hour(self):
		self.assertTrue(is_due("Daily", 2, None, datetime(2026, 11, 15, 2, 0), MON_2AM))
		self.assertFalse(is_due("Daily", 2, None, datetime(2026, 11, 16, 2, 1), MON_2AM))  # already ran today
		self.assertFalse(is_due("Daily", 3, None, None, MON_2AM))

	def test_weekly_on_its_day(self):
		self.assertTrue(is_due("Weekly", 2, "Monday", None, MON_2AM))
		self.assertFalse(is_due("Weekly", 2, "Tuesday", None, MON_2AM))
		self.assertFalse(is_due("", 2, None, None, MON_2AM))


class TestPrune(unittest.TestCase):
	def test_keeps_newest_and_recent(self):
		from test_studio.studio import runs_to_prune

		now = datetime(2026, 11, 14, 12, 0)
		runs = [  # newest first
			{"name": "R5", "test_case": "A", "status": "Running", "creation": datetime(2026, 11, 14)},
			{"name": "R4", "test_case": "A", "status": "Passed", "creation": datetime(2026, 11, 13)},
			{"name": "R3", "test_case": "A", "status": "Failed", "creation": datetime(2026, 11, 12)},
			{"name": "R2", "test_case": "A", "status": "Passed", "creation": datetime(2026, 11, 11)},
			{"name": "R1", "test_case": "B", "status": "Passed", "creation": datetime(2026, 6, 1)},
		]
		self.assertEqual(runs_to_prune(runs, 2, 0, now), ["R2"])  # A keeps its 2 newest finished runs
		self.assertEqual(runs_to_prune(runs, 0, 30, now), ["R1"])  # only by age
		self.assertEqual(runs_to_prune(runs, 0, 0, now), [])
