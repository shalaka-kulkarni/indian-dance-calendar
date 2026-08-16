"""Broad discovery — the scheduled job that searches for events and venues we
don't already know about, so the calendar never depends only on the registry.

Weekly battery of web searches (Brave Search API — generous free tier, key in
BRAVE_API_KEY) over dance-form × metro-area queries plus news-style queries.
Result URLs not belonging to a registered source get fetched and run through
the generic extractors; anything event-shaped enters the normal
classify → validate → publish flow. Hosts that keep producing events are
reported by the healthcheck as proposed new registry sources — the registry
grows itself.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from pipeline.registry import load_sources
from pipeline.scrapers.base import RawEvent, log, make_client
from pipeline.scrapers.html_sources import extract_listing_blocks
from pipeline.scrapers.jsonld import extract_jsonld_events
from pipeline.scrapers.platforms import KEYWORDS

METRO_TERMS = [
    "new york",
    "nyc",
    "brooklyn",
    "queens",
    "new jersey",
    "jersey city",
    "newark nj",
]

EXTRA_QUERIES = [
    "indian dance festival new york 2026",
    "arangetram new york",
    "indian dance performance tickets nyc",
    "nrityagram tour",
    "kathak recital new jersey",
]

# Hosts that are search noise, not event pages.
SKIP_HOSTS = {
    "www.youtube.com", "youtube.com", "www.instagram.com", "instagram.com",
    "www.facebook.com", "facebook.com", "en.wikipedia.org", "www.tiktok.com",
    "twitter.com", "x.com", "www.reddit.com", "reddit.com", "www.yelp.com",
}

MAX_PAGES_PER_RUN = 60  # keep the weekly job polite and bounded


def build_queries() -> list[str]:
    queries = [f"{kw} {metro}" for kw in KEYWORDS for metro in METRO_TERMS[:3]]
    queries += [f"{kw} tickets new york" for kw in KEYWORDS[:6]]
    queries += EXTRA_QUERIES
    return queries


def brave_search(client: httpx.Client, query: str, count: int = 10) -> list[dict]:
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        return []
    resp = client.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": str(count), "country": "us"},
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
    )
    if resp.status_code != 200:
        log.warning("brave search %r -> %s", query, resp.status_code)
        return []
    return (resp.json().get("web") or {}).get("results", [])


def known_hosts() -> set[str]:
    hosts = set()
    for source in load_sources(enabled_only=False):
        if source.url:
            hosts.add(urlparse(source.url).netloc.lower())
    return hosts


def run_discovery(client: httpx.Client | None = None) -> tuple[list[RawEvent], dict[str, int]]:
    """Returns (raw events found, {new_host: event_count} for registry proposals)."""
    if not os.environ.get("BRAVE_API_KEY"):
        log.info("discovery: BRAVE_API_KEY not set, skipping")
        return [], {}
    client = client or make_client()
    registry_hosts = known_hosts()
    candidate_urls: dict[str, str] = {}  # url -> query that found it
    for query in build_queries():
        for result in brave_search(client, query):
            url = result.get("url", "")
            host = urlparse(url).netloc.lower()
            if not url or host in SKIP_HOSTS or host in registry_hosts:
                continue
            candidate_urls.setdefault(url, query)
            if len(candidate_urls) >= MAX_PAGES_PER_RUN:
                break
        if len(candidate_urls) >= MAX_PAGES_PER_RUN:
            break

    found: list[RawEvent] = []
    host_yield: dict[str, int] = {}
    for url in candidate_urls:
        try:
            resp = client.get(url)
            if resp.status_code != 200 or "text/html" not in resp.headers.get(
                "content-type", "text/html"
            ):
                continue
            events = extract_jsonld_events(resp.text, "discovery_search", url)
            if not events:
                events = extract_listing_blocks(resp.text, "discovery_search", url)
            if events:
                host = urlparse(url).netloc.lower()
                host_yield[host] = host_yield.get(host, 0) + len(events)
                found.extend(events)
        except httpx.HTTPError as exc:
            log.debug("discovery fetch failed %s: %s", url, exc)
    return found, host_yield
