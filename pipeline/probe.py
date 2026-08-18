"""Diagnose one source: what does each engine actually see?

A source that yields nothing tells you nothing about why. This walks the same
ladder the sweep does and reports, at each rung, what came back — status codes,
whether the page carries structured data, how many links look event-shaped, what
the sitemap and the plugin API return. Run it from the probe workflow (this
container has no outbound access to venue sites) and read the log.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from pipeline.registry import load_sources
from pipeline.scrapers.base import RawEvent, get, make_client
from pipeline.scrapers.crawl import candidate_links
from pipeline.scrapers.html_sources import extract_listing_blocks
from pipeline.scrapers.jsonld import _walk, extract_jsonld_events
from pipeline.scrapers.sitemap import discover_event_urls
from pipeline.scrapers.tribe import API_PATH, tribe_events

SNIPPET = 400
LD_DUMP = 700
CARD_DUMP = 1200
DATE_TEXT = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b", re.I
)


def _show(label: str, events: list[RawEvent]) -> None:
    print(f"  {label}: {len(events)} events")
    for raw in events[:5]:
        print(f"      - {raw.title[:70]!r} start={raw.start_raw[:30]!r} url={raw.info_url[:80]}")


def _ld_types(html: str, label: str) -> None:
    """A page can carry ld+json we ignore because its @type is not one we accept.
    Print what is actually declared rather than guessing."""
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.find_all("script", type="application/ld+json")
    print(f"  {label}: {len(blocks)} ld+json block(s)")
    for block in blocks[:3]:
        text = (block.string or "").strip()
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            print(f"      UNPARSEABLE: {text[:LD_DUMP]!r}")
            continue
        types, keys = [], []
        for node in _walk(data):
            t = node.get("@type")
            if t:
                types.append(t if isinstance(t, str) else str(t))
                keys.append(sorted(node.keys())[:12])
        print(f"      @types: {types[:12]}")
        for k in keys[:3]:
            print(f"        keys: {k}")
        if not types:
            print(f"        raw: {text[:LD_DUMP]!r}")


def _date_shaped_blocks(html: str) -> None:
    """For pages with no structured data at all: what repeated element carries a
    date? That is where a bespoke parser has to anchor."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in ("time", "[datetime]"):
        nodes = soup.select(tag) if tag.startswith("[") else soup.find_all(tag)
        if nodes:
            print(f"  <{tag}> nodes: {len(nodes)}")
            for n in nodes[:5]:
                print(f"      {str(n)[:160]}")
            return
    hits = soup.find_all(string=DATE_TEXT)
    print(f"  date-shaped text nodes: {len(hits)}")
    for h in hits[:4]:
        parent = h.parent
        cls = parent.get("class") if parent else None
        print(f"      {h.strip()[:60]!r} in <{parent.name if parent else '?'} class={cls}>")
        # A parser has to find the TITLE from here, so show the card that holds
        # the date — guessing its shape is what produced a parser that ran and
        # found nothing.
        card = parent
        for depth in range(1, 4):
            if card is None or card.parent is None:
                break
            card = card.parent
            markup = " ".join(str(card).split())
            print(f"        ancestor -{depth} <{card.name} class={card.get('class')}> "
                  f"len={len(markup)}")
            if depth == 3 or len(markup) > 2500:
                print(f"        markup: {markup[:CARD_DUMP]}")
                break
        else:
            print(f"        markup: {' '.join(str(card).split())[:CARD_DUMP]}")


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
    _ld_types(html, "listing page")
    listing_events = extract_jsonld_events(html, "probe", url)
    _show("jsonld (listing page)", listing_events)
    # Kupferberg's pages DO carry ld+json — all of it Yoast SEO boilerplate with
    # no Event node. Zero events is the signal to show date anchors, not zero
    # blocks.
    if not listing_events:
        _date_shaped_blocks(html)

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
            print(f"  first detail page: {detail.status_code}")
            _ld_types(detail.text, "detail page")
            detail_events = extract_jsonld_events(detail.text, "probe", links[0])
            _show("jsonld (detail page)", detail_events)
            if not detail_events:
                _date_shaped_blocks(detail.text)
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
