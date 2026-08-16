"""Generic ICS calendar-feed scraper for sources that publish .ics feeds."""

from __future__ import annotations

from icalendar import Calendar

from pipeline.scrapers.base import RawEvent


def extract_ics_events(ics_text: str, source_id: str, feed_url: str) -> list[RawEvent]:
    cal = Calendar.from_ical(ics_text)
    events: list[RawEvent] = []
    for component in cal.walk("VEVENT"):
        start = component.get("DTSTART")
        end = component.get("DTEND")
        url = str(component.get("URL", "")) if component.get("URL") else ""
        events.append(
            RawEvent(
                source_id=source_id,
                source_url=feed_url,
                title=str(component.get("SUMMARY", "")),
                start_raw=start.dt.isoformat() if start else "",
                end_raw=end.dt.isoformat() if end else "",
                venue=str(component.get("LOCATION", "")),
                info_url=url or feed_url,
                description=str(component.get("DESCRIPTION", ""))[:600],
            )
        )
    return events
