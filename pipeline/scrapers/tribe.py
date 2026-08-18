"""WordPress "The Events Calendar" REST API.

A large share of mid-size venues run WordPress with the Tribe/The Events Calendar
plugin. Their calendar pages render client-side and their detail pages often
carry no JSON-LD at all, so both the deep crawl and the sitemap fallback come
back empty even though every page fetches fine — that is exactly what Kupferberg
Center and Drom did on the first sweep.

The plugin always exposes the same public REST endpoint, and it returns clean
structured records: title, start, venue, cost, permalink. One request replaces
forty detail-page fetches.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx

from pipeline.scrapers.base import RawEvent, get, log

API_PATH = "/wp-json/tribe/events/v1/events"
PER_PAGE = 50
MAX_PAGES = 4

_TAGS = re.compile(r"<[^>]+>")


def _plain(html: str) -> str:
    return _TAGS.sub(" ", html or "").replace("&nbsp;", " ").strip()


def _cost(event: dict) -> str:
    """Prefer the numeric range; fall back to the venue's own cost string."""
    details = event.get("cost_details") or {}
    values = [v for v in (details.get("values") or []) if str(v).strip()]
    if values:
        symbol = details.get("currency_symbol") or "$"
        lo, hi = str(values[0]), str(values[-1])
        return f"{symbol}{lo}" if lo == hi else f"{symbol}{lo}-{symbol}{hi}"
    return str(event.get("cost") or "").strip()


def _venue(event: dict) -> tuple[str, str]:
    venue = event.get("venue") or {}
    if not isinstance(venue, dict):
        return "", ""
    parts = [
        str(venue.get("address") or ""),
        str(venue.get("city") or ""),
        str(venue.get("state") or venue.get("province") or ""),
    ]
    return str(venue.get("venue") or ""), ", ".join(p for p in parts if p)


def tribe_events(client: httpx.Client, source_id: str, page_url: str) -> list[RawEvent]:
    """Read every upcoming event from the site's Events Calendar API.

    Returns [] for any site that is not running the plugin, so this is safe to
    try on any source before falling through to the other engines.
    """
    endpoint = urljoin(page_url, API_PATH)
    found: list[RawEvent] = []
    for page in range(1, MAX_PAGES + 1):
        try:
            resp = get(client, f"{endpoint}?per_page={PER_PAGE}&page={page}")
        except httpx.HTTPError as exc:
            log.debug("tribe %s: request failed: %s", source_id, exc)
            break
        if resp.status_code != 200:
            break
        try:
            payload = resp.json()
        except ValueError:
            break
        events = payload.get("events") if isinstance(payload, dict) else None
        if not events:
            break
        for event in events:
            if not isinstance(event, dict):
                continue
            venue, address = _venue(event)
            url = str(event.get("url") or "")
            found.append(
                RawEvent(
                    source_id=source_id,
                    source_url=url or page_url,
                    title=_plain(str(event.get("title") or "")),
                    # utc_start_date is naive-UTC text; start_date carries the
                    # venue's local wall time, which is what a reader needs.
                    start_raw=str(event.get("start_date") or ""),
                    end_raw=str(event.get("end_date") or ""),
                    venue=venue,
                    address=address,
                    price_raw=_cost(event),
                    info_url=url,
                    ticket_url=str(event.get("website") or ""),
                    description=_plain(str(event.get("description") or ""))[:600],
                )
            )
        if len(events) < PER_PAGE:
            break
    if found:
        log.info("tribe %s: %d events from the Events Calendar API", source_id, len(found))
    return found
