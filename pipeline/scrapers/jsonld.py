"""Generic schema.org/Event extractor.

Most venue/ticketing platforms (Tessitura, Spektrix, AudienceView, Squarespace
events) embed JSON-LD Event markup. This engine handles any source whose pages
carry it — it is the preferred strategy because structured data rots far more
slowly than HTML layouts.
"""

from __future__ import annotations

import json

from bs4 import BeautifulSoup

from pipeline.scrapers.base import RawEvent

EVENT_TYPES = {
    "Event",
    "TheaterEvent",
    "DanceEvent",
    "MusicEvent",
    "Festival",
    "EducationEvent",
    "ExhibitionEvent",
}


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value) -> str:
    """schema.org values may be strings, dicts with name/@value, or lists."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("@value") or "")
    if isinstance(value, list):
        return _text(value[0]) if value else ""
    return str(value)


def _walk(node):
    """Yield every dict in a JSON-LD structure (handles @graph, nesting, lists)."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _is_event(node: dict) -> bool:
    types = _as_list(node.get("@type"))
    return any(t in EVENT_TYPES for t in types if isinstance(t, str))


def _venue_and_address(node: dict) -> tuple[str, str]:
    loc = node.get("location")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if not isinstance(loc, dict):
        return _text(loc), ""
    venue = _text(loc.get("name"))
    addr = loc.get("address")
    if isinstance(addr, dict):
        parts = [
            _text(addr.get("streetAddress")),
            _text(addr.get("addressLocality")),
            _text(addr.get("addressRegion")),
        ]
        address = ", ".join(p for p in parts if p)
    else:
        address = _text(addr)
    return venue, address


def _prices(node: dict) -> tuple[str, str]:
    """Return (price_raw, ticket_url) from offers."""
    offers = _as_list(node.get("offers"))
    prices: list[str] = []
    ticket_url = ""
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        if not ticket_url:
            ticket_url = _text(offer.get("url"))
        p = offer.get("price")
        if p not in (None, ""):
            prices.append(str(p))
        low, high = offer.get("lowPrice"), offer.get("highPrice")
        if low not in (None, ""):
            prices.append(str(low))
        if high not in (None, ""):
            prices.append(str(high))
    price_raw = "-".join(sorted(set(prices), key=lambda x: float(x) if x.replace(".", "").isdigit() else 0)) if prices else ""
    return price_raw, ticket_url


def extract_jsonld_events(html: str, source_id: str, page_url: str) -> list[RawEvent]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[RawEvent] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _walk(data):
            if not _is_event(node):
                continue
            venue, address = _venue_and_address(node)
            price_raw, ticket_url = _prices(node)
            info_url = _text(node.get("url")) or page_url
            found.append(
                RawEvent(
                    source_id=source_id,
                    source_url=page_url,
                    title=_text(node.get("name")),
                    start_raw=_text(node.get("startDate")),
                    end_raw=_text(node.get("endDate")),
                    venue=venue,
                    address=address,
                    price_raw=price_raw,
                    info_url=info_url,
                    ticket_url=ticket_url,
                    description=_text(node.get("description"))[:600],
                )
            )
    return found
