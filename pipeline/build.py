"""Emit site artifacts from the event store: events.json for the Astro site and
calendar.ics (the subscribable feed).

Two event lists are emitted:
  * upcoming — status PUBLISHED, the live calendar
  * past     — status PAST and previously published, last 6 months, newest
               first, with the ticket link deliberately stripped

The site also gets the canonical filter vocabulary with counts, so filters can
show every borough/form/type and grey out the ones nothing matches.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.models import (
    ArtForm,
    Event,
    EventKind,
    PresenterType,
    Region,
    Status,
    Tradition,
)
from pipeline.registry import load_sources
from pipeline.store import load_all_events

NY_TZ = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "site" / "src" / "data" / "events.json"
SITE_ICS = ROOT / "site" / "public" / "calendar.ics"

ARCHIVE_DAYS = 183  # ~6 months of past events

# Regions we surface as filters even when empty (greyed out in the UI).
FILTER_REGIONS = [
    Region.MANHATTAN,
    Region.BROOKLYN,
    Region.QUEENS,
    Region.BRONX,
    Region.STATEN_ISLAND,
    Region.NEW_JERSEY,
    Region.LONG_ISLAND,
    Region.WESTCHESTER,
]
FILTER_ART_FORMS = [ArtForm.DANCE, ArtForm.MUSIC]
FILTER_TRADITIONS = [t for t in Tradition]
FILTER_PRESENTERS = [
    PresenterType.PROFESSIONAL_COMPANY,
    PresenterType.ACADEMY_STUDENT,
    PresenterType.MIXED,
]
FILTER_KINDS = [
    EventKind.FESTIVAL,
    EventKind.COMMUNITY,
    EventKind.TALK,
    EventKind.WORKSHOP,
]


def price_label(event: Event) -> str | None:
    s = event.scraped
    if s.is_free:
        return "Free"
    if s.price_min is not None:
        if s.price_min == s.price_max:
            return f"${s.price_min:g}"
        return f"${s.price_min:g}–${s.price_max:g}"
    return s.price_note or None


def event_to_site(event: Event, include_tickets: bool = True) -> dict:
    s = event.scraped
    return {
        "id": event.id,
        "title": str(event.effective_scraped_value("title")),
        "start": s.start.isoformat(),
        "end": s.end.isoformat() if s.end else None,
        "additionalDates": [d.isoformat() for d in s.additional_dates],
        "venue": str(event.effective_scraped_value("venue")),
        "address": s.address,
        "region": s.region.value,
        "price": price_label(event),
        "isFree": s.is_free,
        "infoUrl": s.info_url,
        "ticketUrl": (
            (s.ticket_url or None) if include_tickets and s.ticket_url != s.info_url else None
        ),
        "description": s.description_snippet,
        "artForm": event.effective_art_form.value,
        "traditions": [t.value for t in event.effective_traditions],
        "styles": (
            [f.value for f in event.effective_forms]
            + [m.value for m in event.effective_music_styles]
        ),
        "kind": event.ai.kind.value if event.ai else "performance",
        "presenterType": event.effective_presenter_type.value,
        "editorNote": event.curated.editor_note,
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
        for i, start in enumerate([s.start, *s.additional_dates]):
            lines += [
                "BEGIN:VEVENT",
                f"UID:{event.id}-{i}@skyd",
                f"DTSTAMP:{now}",
                f"DTSTART;TZID=America/New_York:{start.strftime('%Y%m%dT%H%M%S')}",
            ]
            if s.end and i == 0 and s.end.date() == start.date():
                lines.append(f"DTEND;TZID=America/New_York:{s.end.strftime('%Y%m%dT%H%M%S')}")
            location = ", ".join(p for p in (s.venue, s.address) if p)
            detail = f"Info: {s.info_url}"
            if s.ticket_url:
                detail += f" | Tickets: {s.ticket_url}"
            lines += [
                f"SUMMARY:{_ics_escape(str(event.effective_scraped_value('title')))}",
                f"LOCATION:{_ics_escape(location)}",
                f"DESCRIPTION:{_ics_escape(detail)}",
                f"URL:{s.info_url}",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _counts(events: list[dict]) -> dict:
    art: dict[str, int] = {}
    traditions: dict[str, int] = {}
    regions: dict[str, int] = {}
    presenters: dict[str, int] = {}
    kinds: dict[str, int] = {}
    free = 0
    for e in events:
        # "both" counts towards dance AND music, so the toggle never hides a
        # community event that is genuinely half of each.
        for a in (["dance", "music"] if e["artForm"] == "both" else [e["artForm"]]):
            art[a] = art.get(a, 0) + 1
        for t in e["traditions"]:
            traditions[t] = traditions.get(t, 0) + 1
        regions[e["region"]] = regions.get(e["region"], 0) + 1
        presenters[e["presenterType"]] = presenters.get(e["presenterType"], 0) + 1
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        if e["isFree"]:
            free += 1
    return {
        "artForms": [{"value": a.value, "count": art.get(a.value, 0)} for a in FILTER_ART_FORMS],
        "traditions": [
            {"value": t.value, "count": traditions.get(t.value, 0)} for t in FILTER_TRADITIONS
        ],
        "regions": [{"value": r.value, "count": regions.get(r.value, 0)} for r in FILTER_REGIONS],
        "presenterTypes": [
            {"value": p.value, "count": presenters.get(p.value, 0)} for p in FILTER_PRESENTERS
        ],
        "kinds": [{"value": k.value, "count": kinds.get(k.value, 0)} for k in FILTER_KINDS],
        "free": free,
    }


def build_site_data() -> dict:
    now = datetime.now(NY_TZ)
    cutoff = now - timedelta(days=ARCHIVE_DAYS)
    all_events = load_all_events()

    upcoming_events = sorted(
        (e for e in all_events if e.status == Status.PUBLISHED),
        key=lambda e: e.scraped.start,
    )
    past_events = sorted(
        (
            e
            for e in all_events
            if e.status == Status.PAST
            and e.was_published
            and e.scraped.start >= cutoff
            # Never surface an archive entry whose info link is known dead.
            and not (e.validation and e.validation.checks.get("links_live") is False)
        ),
        key=lambda e: e.scraped.start,
        reverse=True,
    )

    upcoming = [event_to_site(e) for e in upcoming_events]
    past = [event_to_site(e, include_tickets=False) for e in past_events]

    payload = {
        "generatedAt": now.isoformat(),
        "events": upcoming,
        "pastEvents": past,
        "filters": _counts(upcoming),
        "sourceCount": len([s for s in load_sources(enabled_only=False) if s.enabled]),
    }
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, indent=1))
    SITE_ICS.parent.mkdir(parents=True, exist_ok=True)
    SITE_ICS.write_text(build_ics(upcoming_events))
    return {"published": len(upcoming), "past": len(past)}
