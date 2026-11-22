"""Calendar boundary tests for date events."""

from datetime import date
import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "custom_components" / "divoom_orchestrator" / "date_rules.py"
spec = importlib.util.spec_from_file_location("date_rules", path)
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


class DateRulesTests(unittest.TestCase):
    def test_annual_year_boundary_inclusive(self):
        schedule = {"mode": "annual", "start": "12-20", "end": "01-06"}
        for day in (date(2026, 12, 20), date(2026, 12, 31), date(2027, 1, 1), date(2027, 1, 6)):
            self.assertTrue(rules.is_active(schedule, day))
        for day in (date(2026, 12, 19), date(2027, 1, 7), date(2027, 6, 1)):
            self.assertFalse(rules.is_active(schedule, day))

    def test_once_inclusive(self):
        schedule = {"mode": "once", "start": "2026-12-31", "end": "2027-01-01"}
        self.assertTrue(rules.is_active(schedule, date(2026, 12, 31)))
        self.assertTrue(rules.is_active(schedule, date(2027, 1, 1)))
        self.assertFalse(rules.is_active(schedule, date(2028, 1, 1)))

    def test_leap_day_and_invalid_dates(self):
        schedule = {"mode": "annual", "start": "02-29", "end": "02-29"}
        self.assertTrue(rules.is_active(schedule, date(2028, 2, 29)))
        self.assertFalse(rules.is_active(schedule, date(2027, 2, 28)))
        for schedule in (
            {"mode": "annual", "start": "02-30", "end": "03-01"},
            {"mode": "annual", "start": "2-01", "end": "03-01"},
            {"mode": "once", "start": "2027-02-29", "end": "2027-03-01"},
            {"mode": "once", "start": "2027-03-02", "end": "2027-03-01"},
        ):
            with self.subTest(schedule=schedule), self.assertRaises(ValueError):
                rules.validate_schedule(schedule)
