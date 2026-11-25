"""Calendar rules for date-based events."""

from datetime import date
import re
from typing import Any


def validate_schedule(schedule: dict[str, Any]) -> None:
    """Validate a date schedule."""
    mode = schedule.get("mode")
    if mode == "weekly":
        weekdays = schedule.get("weekdays")
        if (not isinstance(weekdays, list) or not weekdays
                or any(type(day) is not int or day not in range(7) for day in weekdays)
                or len(set(weekdays)) != len(weekdays)):
            raise ValueError("Select distinct weekdays from Monday (0) to Sunday (6)")
        return
    if mode in ("dates_once", "dates_annual"):
        dates = schedule.get("dates")
        if not isinstance(dates, list) or not dates or any(not isinstance(day, str) for day in dates):
            raise ValueError("Select at least one date")
        if len(set(dates)) != len(dates):
            raise ValueError("Dates must be unique")
        for day in dates:
            validate_schedule({"mode": "once" if mode == "dates_once" else "annual",
                               "start": day, "end": day})
        return
    if mode == "holiday":
        calendar = schedule.get("calendar")
        names = schedule.get("holidays")
        if not isinstance(calendar, str) or not re.fullmatch(r"calendar\.[a-z0-9_]+", calendar):
            raise ValueError("Select a calendar entity")
        if (not isinstance(names, list) or not names
                or any(not isinstance(name, str) or not name.strip() or name != name.strip()
                       for name in names)
                or len(set(names)) != len(names)):
            raise ValueError("Select distinct holiday names")
        return
    start = schedule.get("start")
    end = schedule.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError("Both calendar dates are required")
    if mode == "annual":
        if not re.fullmatch(r"\d{2}-\d{2}", start) or not re.fullmatch(r"\d{2}-\d{2}", end):
            raise ValueError("Annual dates must use MM-DD")
        try:
            date.fromisoformat(f"2000-{start}")
            date.fromisoformat(f"2000-{end}")
        except ValueError as err:
            raise ValueError("Invalid annual calendar date") from err
    elif mode == "once":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
            raise ValueError("One-off dates must use YYYY-MM-DD")
        try:
            first = date.fromisoformat(start)
            last = date.fromisoformat(end)
        except ValueError as err:
            raise ValueError("Invalid calendar date") from err
        if last < first:
            raise ValueError("End date must not precede start date")
    else:
        raise ValueError("Unknown date schedule mode")


def is_active(schedule: dict[str, Any], today: date) -> bool:
    """Evaluate the schedule against the caller's local calendar date."""
    validate_schedule(schedule)
    if schedule["mode"] == "weekly":
        return today.weekday() in schedule["weekdays"]
    if schedule["mode"] == "dates_once":
        return today.isoformat() in schedule["dates"]
    if schedule["mode"] == "dates_annual":
        return today.strftime("%m-%d") in schedule["dates"]
    if schedule["mode"] == "holiday":
        raise ValueError("Holiday schedules require calendar events")
    if schedule["mode"] == "once":
        return date.fromisoformat(schedule["start"]) <= today <= date.fromisoformat(schedule["end"])
    current = (today.month, today.day)
    first = tuple(map(int, schedule["start"].split("-")))
    last = tuple(map(int, schedule["end"].split("-")))
    if first <= last:
        return first <= current <= last
    return current >= first or current <= last
