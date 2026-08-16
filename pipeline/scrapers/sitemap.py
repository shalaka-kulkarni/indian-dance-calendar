"""Sitemap fallback for JavaScript-rendered calendars.

Most venue calendars are built client-side, so fetching the listing page yields
an empty shell and there are no links to follow. But those same sites publish a
sitemap for search engines, and their event *detail* pages are server-rendered
with schema.org/Event markup so they show up in Google. So: read the sitemap,
keep the URLs that look like event pages, and extract from those directly.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx

from pipeline.scrapers.base import RawEvent, log
from pipeline.scrapers.jsonld import extract_jsonld_events

SITEMAP_CANDIDATES = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
)

# Sitemaps that themselves look event-shaped get preferred when recursing.
EVENT_SITEMAP_HINT = re.compile(r"(event|performance|show|production|calendar)", re.I)

EVENT_URL_PAT = re.compile(
    r"/(events?|performances?|productions?|shows?|whats-on|calendar|tickets)/[^/]+/?$",
    re.I,
)
SKIP_URL_PAT = re.compile(
    r"/(category|categories|tag|tags|page|author|series|venue|list|archive)/|"
    r"\.(pdf|jpg|jpeg|png|gif|css|js)$",
    re.I,
)

MAX_SITEMAPS = 6
MAX_EVENT_PAGES = 40


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1]


def _parse_sitemap(xml_text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Return (child sitemap urls, [(page url, lastmod)])."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return [], []
    children: list[str] = []
    pages: list[tuple[str, str]] = []
    for node in root:
        tag = _strip_ns(node.tag)
        loc = lastmod = ""
        for child in node:
            name = _strip_ns(child.tag)
            if name == "loc":
                loc = (child.text or "").strip()
            elif name == "lastmod":
                lastmod = (child.text or "").strip()
        if not loc:
            continue
        if tag == "sitemap":
            children.append(loc)
        elif tag == "url":
            pages.append((loc, lastmod))
    return children, pages


def discover_event_urls(client: httpx.Client, site_url: str) -> list[str]:
    origin = f"{urlparse(site_url).scheme}://{urlparse(site_url).netloc}"
    seen_sitemaps: set[str] = set()
    queue: list[str] = [urljoin(origin, path) for path in SITEMAP_CANDIDATES]
    pages: list[tuple[str, str]] = []

    while queue and len(seen_sitemaps) < MAX_SITEMAPS:
        sm_url = queue.pop(0)
        if sm_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sm_url)
        try:
            resp = client.get(sm_url)
        except httpx.HTTPError:
            continue
        if resp.status_code != 200 or "<" not in resp.text[:200]:
            continue
        children, found = _parse_sitemap(resp.text)
        pages.extend(found)
        # Follow event-ish child sitemaps first; ignore the rest.
        queue.extend([c for c in children if EVENT_SITEMAP_HINT.search(c)][:MAX_SITEMAPS])

    # Newest first so a truncated run still gets the freshest listings.
    pages.sort(key=lambda p: p[1], reverse=True)
    urls: list[str] = []
    for url, _ in pages:
        path = urlparse(url).path
        if SKIP_URL_PAT.search(path) or not EVENT_URL_PAT.search(path):
            continue
        urls.append(url)
        if len(urls) >= MAX_EVENT_PAGES:
            break
    return urls


def sitemap_extract(client: httpx.Client, source_id: str, site_url: str) -> list[RawEvent]:
    urls = discover_event_urls(client, site_url)
    if not urls:
        return []
    log.info("sitemap %s: trying %d event pages", source_id, len(urls))
    events: list[RawEvent] = []
    for url in urls:
        try:
            resp = client.get(url)
            if resp.status_code != 200:
                continue
            for raw in extract_jsonld_events(resp.text, source_id, url):
                if not raw.info_url:
                    raw.info_url = url
                events.append(raw)
        except httpx.HTTPError as exc:
            log.debug("sitemap fetch failed %s: %s", url, exc)
    return events
