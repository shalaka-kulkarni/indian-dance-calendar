"""Platform API clients — the long tail of one-off shows at venues on nobody's
list. Keys come from env; a missing key skips the source gracefully (reported
in the sweep summary, never a crash)."""

from __future__ import annotations

import os

import httpx

from pipeline.scrapers.base import RawEvent, make_client

# Dance-only keyword battery, shared by platforms and discovery.
KEYWORDS = [
    "indian classical dance",
    "kathak",
    "bharatanatyam",
    "odissi",
    "kuchipudi",
    "mohiniyattam",
    "manipuri dance",
    "sattriya",
    "kathakali",
    "bollywood dance",
    "garba",
    "bhangra",
    "indian folk dance",
]

NYC_METRO = {"latlong": "40.7128,-74.0060", "radius_miles": 40}


def eventbrite_events(client: httpx.Client | None = None) -> list[RawEvent]:
    token = os.environ.get("EVENTBRITE_TOKEN")
    if not token:
        return []
    client = client or make_client()
    found: list[RawEvent] = []
    for keyword in KEYWORDS:
        resp = client.get(
            "https://www.eventbriteapi.com/v3/events/search/",
            params={
                "q": keyword,
                "location.latitude": "40.7128",
                "location.longitude": "-74.0060",
                "location.within": f"{NYC_METRO['radius_miles']}mi",
                "expand": "venue,ticket_availability",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            continue
        for ev in resp.json().get("events", []):
            venue = (ev.get("venue") or {}).get("name", "")
            address = ((ev.get("venue") or {}).get("address") or {}).get(
                "localized_address_display", ""
            )
            tickets = ev.get("ticket_availability") or {}
            price_parts = []
            for bound in ("minimum_ticket_price", "maximum_ticket_price"):
                p = tickets.get(bound) or {}
                if p.get("major_value"):
                    price_parts.append(p["major_value"])
            found.append(
                RawEvent(
                    source_id="eventbrite",
                    source_url=resp.url and str(resp.url) or "",
                    title=(ev.get("name") or {}).get("text", ""),
                    start_raw=(ev.get("start") or {}).get("local", ""),
                    end_raw=(ev.get("end") or {}).get("local", ""),
                    venue=venue,
                    address=address,
                    price_raw="-".join(price_parts) if price_parts else (
                        "Free" if tickets.get("is_free") else ""
                    ),
                    info_url=ev.get("url", ""),
                    ticket_url=ev.get("url", ""),
                    description=((ev.get("description") or {}).get("text") or "")[:600],
                )
            )
    return found


def ticketmaster_events(client: httpx.Client | None = None) -> list[RawEvent]:
    key = os.environ.get("TICKETMASTER_KEY")
    if not key:
        return []
    client = client or make_client()
    found: list[RawEvent] = []
    for keyword in KEYWORDS:
        resp = client.get(
            "https://app.ticketmaster.com/discovery/v2/events.json",
            params={
                "keyword": keyword,
                "latlong": NYC_METRO["latlong"],
                "radius": str(NYC_METRO["radius_miles"]),
                "unit": "miles",
                "apikey": key,
                "size": "50",
            },
        )
        if resp.status_code != 200:
            continue
        for ev in (resp.json().get("_embedded") or {}).get("events", []):
            venues = (ev.get("_embedded") or {}).get("venues", [])
            venue = venues[0]["name"] if venues else ""
            address = ""
            if venues:
                city = (venues[0].get("city") or {}).get("name", "")
                line = (venues[0].get("address") or {}).get("line1", "")
                address = ", ".join(p for p in (line, city) if p)
            prices = ev.get("priceRanges") or []
            price_raw = ""
            if prices:
                price_raw = f"{prices[0].get('min', '')}-{prices[0].get('max', '')}"
            start = (ev.get("dates") or {}).get("start") or {}
            found.append(
                RawEvent(
                    source_id="ticketmaster",
                    source_url=str(resp.url),
                    title=ev.get("name", ""),
                    start_raw=start.get("dateTime") or start.get("localDate", ""),
                    venue=venue,
                    address=address,
                    price_raw=price_raw,
                    info_url=ev.get("url", ""),
                    ticket_url=ev.get("url", ""),
                    description=(ev.get("info") or "")[:600],
                )
            )
    return found
