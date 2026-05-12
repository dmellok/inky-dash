"""Sanity tests for the ICS parser.

Covers the bits we hand-rolled instead of pulling in the icalendar
package: line unfolding, parameter stripping, timed UTC events,
all-day DATE values, and the SUMMARY/LOCATION text-value escape rules.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SERVER = importlib.util.spec_from_file_location(
    "calendar_server",
    Path(__file__).parent.parent / "server.py",
)
assert _SERVER is not None and _SERVER.loader is not None
calendar_server = importlib.util.module_from_spec(_SERVER)
_SERVER.loader.exec_module(calendar_server)


SAMPLE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "BEGIN:VEVENT\r\n"
    "SUMMARY:Standup\r\n"
    "DTSTART:20261015T093000Z\r\n"
    "DTEND:20261015T100000Z\r\n"
    "LOCATION:Zoom\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "SUMMARY:Holiday\r\n"
    "DTSTART;VALUE=DATE:20261020\r\n"
    "DTEND;VALUE=DATE:20261021\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "SUMMARY:Wrapped \r\n"
    " title across two lines\r\n"
    "DTSTART:20261022T140000Z\r\n"
    "DESCRIPTION:Hello\\, world\\nNew line here\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_parses_timed_utc_event() -> None:
    events = calendar_server._parse_ics(SAMPLE)
    standup = next(e for e in events if e["title"] == "Standup")
    assert standup["location"] == "Zoom"
    assert standup["start_iso"].startswith("2026-10-15T09:30:00")
    assert standup["end_iso"].startswith("2026-10-15T10:00:00")
    assert standup["all_day"] is False


def test_parses_all_day_event() -> None:
    events = calendar_server._parse_ics(SAMPLE)
    holiday = next(e for e in events if e["title"] == "Holiday")
    assert holiday["all_day"] is True
    assert holiday["start_iso"].startswith("2026-10-20")


def test_unfolds_continuation_lines() -> None:
    events = calendar_server._parse_ics(SAMPLE)
    wrapped = next(e for e in events if e["title"].startswith("Wrapped"))
    assert wrapped["title"] == "Wrapped title across two lines"


def test_handles_missing_dtstart() -> None:
    bad = "BEGIN:VEVENT\r\nSUMMARY:Headless\r\nEND:VEVENT\r\n"
    assert calendar_server._parse_ics(bad) == []
