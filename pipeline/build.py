"""Emit site artifacts from the event store: events.json for the Astro site and
calendar.ics (the subscribable feed). Only PUBLISHED events are emitted — the
publish gate lives in validate.py, not here."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.models import Event, Status
from pipeline.registry import load_sources
from pipeline.store import load_all_events

NY_TZ = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "site" / "src" / "data" / "events.json"
SITE_ICS = ROOT / "site" / "public" / "calendar.ics"


def event_to_site(event: Event, circuit_by_source: dict[str, str] | None = None) -> dict:
    s = event.scraped
    circuit_by_source = circuit_by_source or {}
    circuits = sorted({
        circuit_by_source.get(r.source_id, "")
        for r in s.sources
        if circuit_by_source.get(r.source_id)
    })
    price = None
    if s.is_free:
        price = "Free"
    elif s.price_min is not None:
        price = (
            f"${s.price_min:g}" if s.price_min == s.price_max else f"${s.price_min:g}–${s.price_max:g}"
        )
    elif s.price_note:
        price = s.price_note
    return {
        "id": event.id,
        "title": str(event.effective_scraped_value("title")),
        "start": s.start.isoformat(),
        "end": s.end.isoformat() if s.end else None,
        "additionalDates": [d.isoformat() for d in s.additional_dates],
        "venue": str(event.effective_scraped_value("venue")),
        "address": s.address,
        "region": s.region.value,
        "price": price,
        "priceNote": s.price_note,
        "isFree": s.is_free,
        "infoUrl": s.info_url,
        "ticketUrl": s.ticket_url,
        "description": s.description_snippet,
        "forms": [f.value for f in event.effective_forms],
        "kind": event.ai.kind.value if event.ai else "performance",
        "presenterType": event.effective_presenter_type.value,
        "editorNote": event.curated.editor_note,
        "circuits": circuits,
        "sources": [
            {"id": r.source_id, "url": r.url, "lastSeen": r.last_seen.isoformat()}
            for r in s.sources
        ],
        "lastValidated": event.validation.validated_at.isoformat()
        if event.validation and event.validation.validated_at
        else None,
    }


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(events: list[Event]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//skyd//NYC Indian Dance Calendar//EN",
        "X-WR-CALNAME:NYC Indian Dance",
        "X-WR-TIMEZONE:America/New_York",
    ]
    now = datetime.now(NY_TZ).strftime("%Y%m%dT%H%M%S")
    for event in events:
        s = event.scraped
        dates = [s.start, *s.additional_dates]
        for i, start in enumerate(dates):
            uid = f"{event.id}-{i}@skyd"
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now}",
                f"DTSTART;TZID=America/New_York:{start.strftime('%Y%m%dT%H%M%S')}",
            ]
            if s.end and i == 0 and s.end.date() == start.date():
                lines.append(f"DTEND;TZID=America/New_York:{s.end.strftime('%Y%m%dT%H%M%S')}")
            summary = str(event.effective_scraped_value("title"))
            location = ", ".join(p for p in (s.venue, s.address) if p)
            lines += [
                f"SUMMARY:{_ics_escape(summary)}",
                f"LOCATION:{_ics_escape(location)}",
                f"DESCRIPTION:{_ics_escape('Info: ' + s.info_url + (' | Tickets: ' + s.ticket_url if s.ticket_url else ''))}",
                f"URL:{s.info_url}",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def build_site_data() -> dict:
    events = [e for e in load_all_events() if e.status == Status.PUBLISHED]
    events.sort(key=lambda e: e.scraped.start)
    sources = load_sources(enabled_only=False)
    circuit_by_source = {s.id: s.circuit.value for s in sources}
    payload = {
        "generatedAt": datetime.now(NY_TZ).isoformat(),
        "events": [event_to_site(e, circuit_by_source) for e in events],
        "sources": [
            {"id": s.id, "name": s.name, "circuit": s.circuit.value, "url": s.url}
            for s in sources
            if s.enabled
        ],
    }
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, indent=1))
    SITE_ICS.parent.mkdir(parents=True, exist_ok=True)
    SITE_ICS.write_text(build_ics(events))
    return {"published": len(events)}
