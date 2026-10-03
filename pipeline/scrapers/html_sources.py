"""Bespoke HTML parsers for sources without structured data.

Written defensively and validated on the first live run (this build environment
cannot reach the sites): each parser tries JSON-LD first via the generic engine,
then falls back to HTML heuristics. A parser that finds nothing reports zero
events — the healthcheck workflow turns repeated zeros into a loud GitHub issue
rather than letting a source rot silently.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from pipeline.scrapers.base import RawEvent
from pipeline.scrapers.jsonld import extract_jsonld_events

# Matches "Sep 19, 2026", "September 19-20, 2026", "19 September 2026", "9/19/2026"
DATE_PAT = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:\s*[-–]\s*\d{1,2})?,?\s+\d{4}"
    r"|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)

PRICE_PAT = re.compile(r"(free|\$\s?\d+(?:\.\d{2})?(?:\s*[-–—]\s*\$?\s?\d+(?:\.\d{2})?)?)", re.IGNORECASE)


def _block_to_event(block, source_id: str, page_url: str) -> RawEvent | None:
    """Heuristic extraction from a listing block: needs a link + a date to count."""
    text = block.get_text(" ", strip=True)
    date_match = DATE_PAT.search(text)
    if not date_match:
        return None
    link = block.find("a", href=True)
    if link is None:
        return None
    title = link.get_text(" ", strip=True) or text[:80]
    heading = block.find(["h1", "h2", "h3", "h4"])
    if heading is not None:
        heading_text = heading.get_text(" ", strip=True)
        if heading_text:
            title = heading_text
    price_match = PRICE_PAT.search(text)
    return RawEvent(
        source_id=source_id,
        source_url=page_url,
        title=title,
        start_raw=date_match.group(1),
        price_raw=price_match.group(1) if price_match else "",
        info_url=urljoin(page_url, link["href"]),
        description=text[:600],
    )


def extract_listing_blocks(
    html: str, source_id: str, page_url: str, selectors: list[str] | None = None
) -> list[RawEvent]:
    """Generic fallback: JSON-LD first, then likely listing blocks."""
    events = extract_jsonld_events(html, source_id, page_url)
    if events:
        return events
    soup = BeautifulSoup(html, "html.parser")
    selectors = selectors or [
        "article",
        "li.event, li.event-item, div.event, div.event-item, div.event-card",
        "div.views-row",  # Drupal listings (common among arts orgs)
        "div.eventlist-event",  # Squarespace
    ]
    seen_urls: set[str] = set()
    found: list[RawEvent] = []
    for selector in selectors:
        for block in soup.select(selector):
            raw = _block_to_event(block, source_id, page_url)
            if raw and raw.info_url not in seen_urls:
                seen_urls.add(raw.info_url)
                found.append(raw)
        if found:
            break
    return found


def extract_narthaki(html: str, source_id: str, page_url: str) -> list[RawEvent]:
    """narthaki.com/info/fevents.html — long-running hand-maintained listing.
    Entries are text lines/paragraphs with date, event, venue, city. We keep only
    NY-metro entries; classification confirms relevance downstream."""
    soup = BeautifulSoup(html, "html.parser")
    ny_pat = re.compile(
        r"new york|nyc|manhattan|brooklyn|queens|bronx|staten island|new jersey|"
        r"jersey city|newark|long island|westchester",
        re.IGNORECASE,
    )
    found: list[RawEvent] = []
    for block in soup.find_all(["p", "li", "tr", "div"]):
        text = block.get_text(" ", strip=True)
        if not (20 < len(text) < 800):
            continue
        if not ny_pat.search(text):
            continue
        date_match = DATE_PAT.search(text)
        if not date_match:
            continue
        link = block.find("a", href=True)
        found.append(
            RawEvent(
                source_id=source_id,
                source_url=page_url,
                title=text[:120],
                start_raw=date_match.group(1),
                info_url=urljoin(page_url, link["href"]) if link else page_url,
                description=text[:600],
            )
        )
    # De-dupe nested blocks that matched the same text.
    unique: dict[str, RawEvent] = {}
    for event in found:
        key = event.description[:200]
        if key not in unique:
            unique[key] = event
    return list(unique.values())


def extract_eventin(html: str, source_id: str, page_url: str) -> list[RawEvent]:
    """The "EventIn" WordPress plugin, which prefixes every class with `etn-`.

    CMANA runs it. The plugin emits no structured data, its only crawlable links
    are a membership form and a password reset, and its sitemap lists no events —
    but the listing markup itself is clean and stable, one `.etn-event-item` per
    event with the title, date, location and blurb in named children.
    """
    events = extract_jsonld_events(html, source_id, page_url)
    if events:
        return events

    soup = BeautifulSoup(html, "html.parser")
    found: list[RawEvent] = []
    seen: set[str] = set()
    for item in soup.select(".etn-event-item"):
        link = item.select_one(".etn-event-title a, .etn-title a") or item.select_one("a[href]")
        # The card's own heading is best, but the archive template puts the
        # thumbnail link first and labels it with the event name.
        title = (link.get_text(" ", strip=True) if link else "") or (
            link.get("aria-label", "") if link else ""
        )
        # The plugin's templates disagree about where the date goes: the single
        # listing puts it in .etn-event-date, the archive in .etn-event-footer.
        # Read whichever exists, then fall back to the card's own text.
        date_match = None
        for selector in (".etn-event-date", ".etn-event-footer"):
            node = item.select_one(selector)
            if node is not None:
                date_match = DATE_PAT.search(node.get_text(" ", strip=True))
                if date_match:
                    break
        if date_match is None:
            date_match = DATE_PAT.search(item.get_text(" ", strip=True))
        if not (title and date_match):
            continue
        info_url = urljoin(page_url, link["href"]) if link and link.get("href") else page_url
        if info_url in seen:
            continue
        seen.add(info_url)

        location = item.select_one(".etn-event-location")
        blurb = item.select_one(".etn-title-info p")
        price = PRICE_PAT.search(item.get_text(" ", strip=True))
        found.append(
            RawEvent(
                source_id=source_id,
                source_url=page_url,
                title=title,
                start_raw=date_match.group(1),
                # The plugin runs venue and street address together in one line;
                # normalize.py reads the region out of it either way.
                address=location.get_text(" ", strip=True) if location else "",
                price_raw=price.group(1) if price else "",
                info_url=info_url,
                description=blurb.get_text(" ", strip=True)[:600] if blurb else "",
            )
        )
    return found


# ── The Dance Enthusiast ─────────────────────────────────────────────────────
# dance-enthusiast.com/dance-listings/events is the one listing where both
# circuits already appear. No structured data anywhere: each day is an
# <h2 class="date_col_heading"> followed by <a class="listing_container"> cards
# whose title sits in .imageTitleB h2 (or the thumbnail's alt). Out-of-town
# listings carry a "CITY, ST:" prefix, which is how a nationwide page is kept
# to the metro.
TDE_CITY_PREFIX = re.compile(r"^\s*([A-Z][A-Z .'&-]+),\s*([A-Z]{2})\s*:", re.I)
TDE_METRO_STATES = {"NY", "NJ"}
TDE_FAR_NY = re.compile(r"\b(buffalo|rochester|syracuse|albany|ithaca|saratoga|binghamton)\b", re.I)
# The card text runs title, venue, then "Sun. October, 4 @ 4:00pm". Everything
# between the title and the weekday is the venue.
TDE_WHEN = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+\d{1,2}"
    r"(?:\s*@\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)))?",
    re.I,
)


def extract_dance_enthusiast(html: str, source_id: str, page_url: str) -> list[RawEvent]:
    events = extract_jsonld_events(html, source_id, page_url)
    if events:
        return events
    soup = BeautifulSoup(html, "html.parser")
    col = soup.select_one(".col_1110") or soup
    found: list[RawEvent] = []
    seen: set[str] = set()
    current_date = ""
    for node in col.descendants:
        if getattr(node, "name", None) == "h2" and "date_col_heading" in (node.get("class") or []):
            m = DATE_PAT.search(node.get_text(" ", strip=True))
            current_date = m.group(1) if m else ""
            continue
        if getattr(node, "name", None) != "a" or "listing_container" not in (node.get("class") or []):
            continue
        href = node.get("href") or ""
        if not href or not current_date:
            continue
        url = urljoin(page_url, href)
        if url in seen:
            continue
        heading = node.select_one(".imageTitleB h2")
        img = node.find("img")
        title = (heading.get_text(" ", strip=True) if heading else "") or (img.get("alt", "") if img else "")
        title = title.strip()
        if not title:
            continue
        address = ""
        prefix = TDE_CITY_PREFIX.match(title)
        if prefix:
            city, state = prefix.group(1), prefix.group(2).upper()
            if state not in TDE_METRO_STATES or TDE_FAR_NY.search(city):
                continue
            title = title[prefix.end():].strip()
            address = f"{city.strip().title()}, {state}"
        seen.add(url)
        text = node.get_text(" ", strip=True)
        venue, when = tde_venue_and_time(text, title)
        price = PRICE_PAT.search(text)
        found.append(
            RawEvent(
                source_id=source_id,
                source_url=page_url,
                title=title,
                start_raw=f"{current_date} {when}".strip(),
                venue=venue,
                address=address,
                price_raw=price.group(1) if price else "",
                info_url=url,
                description=text[:600],
            )
        )
    return found


def tde_venue_and_time(card_text: str, title: str) -> tuple[str, str]:
    """Split a Dance Enthusiast card's text into venue and clock time.

    The card reads "<title> <venue> Sun. October, 4 @ 4:00pm". The title is
    known, the weekday marks where the venue ends, and the time follows the @.
    Either part may be missing; what is not there comes back empty.
    """
    text = " ".join(card_text.split())
    if title and text.lower().startswith(title.lower()):
        text = text[len(title):].strip()
    m = TDE_WHEN.search(text)
    if not m:
        return "", ""
    venue = text[: m.start()].strip(" -–—|,")
    return venue, (m.group(1) or "").replace(" ", "")


# Gibney's calendar page is rendered client-side from an inline array:
#   var eventDates = [{"start":"2026-12-02","title":...,"url":...,
#                      "print_start_time":"10:00 am","end":"2026-12-02",...}]
# Detail pages carry no Event markup and the Events Calendar API answers 404,
# so this array is the only machine-readable listing the site has.
GIBNEY_FEED = re.compile(r"var\s+eventDates\s*=\s*(\[.*?\])\s*;", re.S)


def extract_gibney(html: str, source_id: str, page_url: str) -> list[RawEvent]:
    events = extract_jsonld_events(html, source_id, page_url)
    if events:
        return events
    m = GIBNEY_FEED.search(html)
    if not m:
        return []
    try:
        rows = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    found: list[RawEvent] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = " ".join(str(row.get("title") or "").split())
        start = str(row.get("start") or "")
        url = urljoin(page_url, str(row.get("url") or ""))
        if not title or not start or url in seen:
            continue
        seen.add(url)
        end = str(row.get("end") or "")
        start_time = str(row.get("print_start_time") or "")
        end_time = str(row.get("print_end_time") or "")
        found.append(
            RawEvent(
                source_id=source_id,
                source_url=page_url,
                title=title,
                start_raw=f"{start} {start_time}".strip(),
                end_raw=f"{end} {end_time}".strip() if end and end != start else "",
                venue="Gibney",
                address="New York, NY",
                info_url=url,
                description=" ".join(str(row.get("excerpt") or "").split())[:600],
            )
        )
    return found
