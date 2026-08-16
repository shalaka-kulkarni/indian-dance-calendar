"""RawEvent -> Scraped: parse dates into America/New_York, parse price text
into a range, infer region from venue/address. Unparseable values are kept
verbatim (price_note) rather than guessed — never fabricate."""

from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dateutil import parser as dateparser

from pipeline.models import Region, Scraped, SourceRecord
from pipeline.scrapers.base import RawEvent
from pipeline.store import content_hash

NY_TZ = ZoneInfo("America/New_York")

PRICE_NUM = re.compile(r"\$?\s?(\d+(?:\.\d{2})?)")

REGION_HINTS: list[tuple[re.Pattern, Region]] = [
    (re.compile(r"brooklyn|\bbam\b", re.I), Region.BROOKLYN),
    (re.compile(r"queens|flushing|astoria|laguardia", re.I), Region.QUEENS),
    (re.compile(r"bronx", re.I), Region.BRONX),
    (re.compile(r"staten island", re.I), Region.STATEN_ISLAND),
    (re.compile(r"new jersey|\bnj\b|newark|jersey city|new brunswick|south orange|hoboken", re.I), Region.NEW_JERSEY),
    (re.compile(r"long island|hempstead|brookville", re.I), Region.LONG_ISLAND),
    (re.compile(r"westchester|yonkers|white plains|tarrytown", re.I), Region.WESTCHESTER),
    (re.compile(r"manhattan|new york,?\s*ny|nyc|broadway|lincoln center|chelsea|harlem", re.I), Region.MANHATTAN),
]


def parse_when(raw: str) -> datetime | None:
    """Parse a date/datetime string; assume America/New_York when no tz given.
    Handles day ranges like 'Sep 19-20, 2026' by returning the first day."""
    if not raw:
        return None
    cleaned = re.sub(r"(\d{1,2})\s*[-–]\s*\d{1,2}(,?\s+\d{4})", r"\1\2", raw.strip())
    try:
        parsed = dateparser.parse(cleaned, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=NY_TZ)
    return parsed


def parse_price(raw: str) -> tuple[float | None, float | None, bool, str]:
    """Return (min, max, is_free, note). Verbatim text goes to note when the
    numbers don't tell the whole story."""
    if not raw:
        return None, None, False, ""
    if re.search(r"\bfree\b", raw, re.I):
        return 0.0, 0.0, True, raw.strip() if raw.strip().lower() != "free" else ""
    numbers = [float(m) for m in PRICE_NUM.findall(raw)]
    if not numbers:
        return None, None, False, raw.strip()
    note = raw.strip() if re.search(r"from|\+|donation|suggested", raw, re.I) else ""
    return min(numbers), max(numbers), False, note


def infer_region(venue: str, address: str, fallback: Region = Region.UNKNOWN) -> Region:
    haystack = f"{venue} {address}"
    for pattern, region in REGION_HINTS:
        if pattern.search(haystack):
            return region
    return fallback


def normalize(raw: RawEvent, source_region: Region = Region.UNKNOWN, today: date | None = None) -> Scraped | None:
    """Returns None when the raw record can't meet the floor: a title, a
    parseable future-ish date, and some URL."""
    title = re.sub(r"\s+", " ", raw.title).strip()
    start = parse_when(raw.start_raw)
    info_url = raw.info_url or raw.source_url
    if not title or start is None or not info_url:
        return None
    end = parse_when(raw.end_raw)
    if end is not None and end < start:
        end = None
    price_min, price_max, is_free, price_note = parse_price(raw.price_raw)
    scraped = Scraped(
        title=title[:200],
        start=start,
        end=end,
        venue=re.sub(r"\s+", " ", raw.venue).strip()[:120],
        address=raw.address.strip()[:200],
        region=infer_region(raw.venue, raw.address, source_region),
        price_min=price_min,
        price_max=price_max,
        is_free=is_free,
        price_note=price_note[:120],
        info_url=info_url,
        ticket_url=raw.ticket_url if raw.ticket_url != info_url else raw.ticket_url,
        description_snippet=re.sub(r"\s+", " ", raw.description).strip()[:600],
        sources=[
            SourceRecord(
                source_id=raw.source_id,
                url=info_url,
                first_seen=today or date.today(),
                last_seen=today or date.today(),
            )
        ],
    )
    scraped.content_hash = content_hash(scraped)
    return scraped
