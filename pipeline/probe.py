"""Diagnose one source: what does each engine actually see?

A source that yields nothing tells you nothing about why. This walks the same
ladder the sweep does and reports, at each rung, what came back — status codes,
whether the page carries structured data, how many links look event-shaped, what
the sitemap and the plugin API return. Run it from the probe workflow (this
container has no outbound access to venue sites) and read the log.
"""

from __future__ import annotations

from urllib.parse import urljoin

import httpx

from pipeline.registry import load_sources
from pipeline.scrapers.base import RawEvent, get, make_client
from pipeline.scrapers.crawl import candidate_links
from pipeline.scrapers.html_sources import extract_listing_blocks
from pipeline.scrapers.jsonld import extract_jsonld_events
from pipeline.scrapers.sitemap import discover_event_urls
from pipeline.scrapers.tribe import API_PATH, tribe_events

SNIPPET = 400


def _show(label: str, events: list[RawEvent]) -> None:
    print(f"  {label}: {len(events)} events")
    for raw in events[:5]:
        print(f"      - {raw.title[:70]!r} start={raw.start_raw[:30]!r} url={raw.info_url[:80]}")


def probe(url: str) -> None:
    print(f"\n=== probing {url} ===")
    client = make_client()

    try:
        resp = get(client, url)
    except httpx.HTTPError as exc:
        print(f"  FETCH FAILED: {type(exc).__name__}: {exc}")
        return

    print(f"  status: {resp.status_code}  final url: {resp.url}")
    print(f"  content-type: {resp.headers.get('content-type', '?')}")
    print(f"  server: {resp.headers.get('server', '?')}")
    if resp.status_code != 200:
        print(f"  body starts: {resp.text[:SNIPPET]!r}")
        return

    html = resp.text
    print(f"  html length: {len(html)}")

    # Rung 1: structured data on the listing page itself.
    ld_count = html.count("application/ld+json")
    print(f"  ld+json blocks on page: {ld_count}")
    _show("jsonld (listing page)", extract_jsonld_events(html, "probe", url))

    # Rung 2: the generic HTML block reader.
    _show("html blocks", extract_listing_blocks(html, "probe", url))

    # Rung 3: what the deep crawl would follow, and what one detail page holds.
    links = candidate_links(html, url)
    print(f"  deep-crawl candidate links: {len(links)}")
    for link in links[:8]:
        print(f"      {link}")
    if links:
        try:
            detail = get(client, links[0])
            print(f"  first detail page: {detail.status_code}, ld+json blocks="
                  f"{detail.text.count('application/ld+json')}")
            _show("jsonld (detail page)", extract_jsonld_events(detail.text, "probe", links[0]))
        except httpx.HTTPError as exc:
            print(f"  detail fetch failed: {exc}")

    # Rung 4: the sitemap.
    try:
        sitemap_urls = discover_event_urls(client, url)
        print(f"  sitemap event urls: {len(sitemap_urls)}")
        for su in sitemap_urls[:8]:
            print(f"      {su}")
    except httpx.HTTPError as exc:
        print(f"  sitemap failed: {exc}")

    # Rung 5: the WordPress Events Calendar API.
    endpoint = urljoin(url, API_PATH)
    try:
        api_resp = get(client, f"{endpoint}?per_page=5")
        print(f"  tribe API {endpoint}: {api_resp.status_code}")
        print(f"      body starts: {api_resp.text[:200]!r}")
    except httpx.HTTPError as exc:
        print(f"  tribe API failed: {exc}")
    _show("tribe API (parsed)", tribe_events(client, "probe", url))


def probe_sources(targets: list[str]) -> None:
    """Targets are source ids from the registry, or bare URLs."""
    by_id = {s.id: s for s in load_sources(enabled_only=False)}
    for target in targets:
        source = by_id.get(target)
        probe(source.url if source else target)
