"""Deep-crawl fallback for JS-rendered listing pages.

Many venue sites render their calendar client-side, so the listing page HTML
contains no events — but their event *detail* pages are server-rendered with
schema.org/Event JSON-LD for SEO. When the listing page yields nothing, follow
links that look like event detail pages (same host, bounded count) and extract
from each.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from pipeline.scrapers.base import RawEvent, log
from pipeline.scrapers.jsonld import extract_jsonld_events

EVENT_PATH_PAT = re.compile(
    r"/(event|events|whats-on|performance|performances|production|show|shows|"
    r"calendar|pdps|program)s?/[^/]+",
    re.IGNORECASE,
)

# Links that match the pattern but are never event detail pages.
SKIP_PATH_PAT = re.compile(
    r"/(category|tag|page|month|week|day|list|archive|past|venue|series)(/|$)|"
    r"\.(pdf|jpg|png|ics)$|\?ical=|#",
    re.IGNORECASE,
)

MAX_DETAIL_PAGES = 25


def candidate_links(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(page_url).netloc
    found: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        url = urljoin(page_url, a["href"]).split("#")[0]
        parsed = urlparse(url)
        if parsed.netloc != host:
            continue
        if not EVENT_PATH_PAT.search(parsed.path):
            continue
        if SKIP_PATH_PAT.search(parsed.path) or SKIP_PATH_PAT.search(url):
            continue
        if url == page_url or url in seen:
            continue
        seen.add(url)
        found.append(url)
        if len(found) >= MAX_DETAIL_PAGES:
            break
    return found


def deep_extract(
    client: httpx.Client, source_id: str, page_url: str, listing_html: str
) -> list[RawEvent]:
    events: list[RawEvent] = []
    links = candidate_links(listing_html, page_url)
    log.info("deep crawl %s: following %d detail links", source_id, len(links))
    for url in links:
        try:
            resp = client.get(url)
            if resp.status_code != 200:
                continue
            for raw in extract_jsonld_events(resp.text, source_id, url):
                # Detail-page markup sometimes omits its own URL; anchor it here.
                if not raw.info_url or raw.info_url == url.split("?")[0]:
                    raw.info_url = url
                events.append(raw)
        except httpx.HTTPError as exc:
            log.debug("deep crawl fetch failed %s: %s", url, exc)
    return events
