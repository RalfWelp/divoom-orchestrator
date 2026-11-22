"""Calendar rules for date-based events."""

from datetime import date
import re
from typing import Any


def validate_schedule(schedule: dict[str, Any]) -> None:
    """Validate inclusive one-off or yearly calendar boundaries."""
    mode = schedule.get("mode")
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
    if schedule["mode"] == "once":
        return date.fromisoformat(schedule["start"]) <= today <= date.fromisoformat(schedule["end"])
    current = (today.month, today.day)
    first = tuple(map(int, schedule["start"].split("-")))
    last = tuple(map(int, schedule["end"].split("-")))
    if first <= last:
        return first <= current <= last
    return current >= first or current <= last
