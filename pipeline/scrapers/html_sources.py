"""Bespoke HTML parsers for sources without structured data.

Written defensively and validated on the first live run (this build environment
cannot reach the sites): each parser tries JSON-LD first via the generic engine,
then falls back to HTML heuristics. A parser that finds nothing reports zero
events — the healthcheck workflow turns repeated zeros into a loud GitHub issue
rather than letting a source rot silently.
"""

from __future__ import annotations

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
        link = item.select_one(".etn-event-title a, .etn-title a")
        title = link.get_text(" ", strip=True) if link else ""
        date_node = item.select_one(".etn-event-date")
        date_text = date_node.get_text(" ", strip=True) if date_node else ""
        date_match = DATE_PAT.search(date_text)
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
