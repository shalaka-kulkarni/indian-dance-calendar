"""Shared scraping plumbing: polite fetching, the RawEvent intermediate shape,
and per-source error isolation so one broken source never sinks a sweep."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

log = logging.getLogger("skyd")

# A standard browser UA: several venue sites' WAFs reject unfamiliar agents
# outright (403), which starves the calendar. Volume stays polite either way —
# a few dozen pages per source, three times a week.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Some WAFs (Cloudflare, Akamai, Sitecore) reject a request that sends no Accept
# header at all with 406 Not Acceptable — Tilles Center and State Theatre NJ both
# did. Send what a browser sends.
ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)

DEFAULT_TIMEOUT = 30.0

# 429/503 are "slow down", not "go away". One backoff retry recovers Navatman and
# the Met, which rate-limit the first hit of a sweep and then serve fine.
RETRY_STATUSES = frozenset({429, 503})
RETRY_WAIT_SECONDS = 5.0
MAX_RETRY_WAIT_SECONDS = 30.0


@dataclass
class RawEvent:
    """What a scraper emits before normalization. Strings stay verbatim from the
    source; normalize.py handles parsing. Facts only — nothing generated."""

    source_id: str
    source_url: str  # the page/feed this came from
    title: str = ""
    start_raw: str = ""  # ISO or verbatim date text
    end_raw: str = ""
    venue: str = ""
    address: str = ""
    price_raw: str = ""  # verbatim price text ("$25–$45", "Free", "from $30")
    info_url: str = ""  # event's own info page
    ticket_url: str = ""  # offers/booking URL when distinct
    description: str = ""
    extra: dict = field(default_factory=dict)


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": USER_AGENT,
            "Accept": ACCEPT,
            "Accept-Language": "en-US,en",
        },
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )


def _retry_wait(resp: httpx.Response) -> float:
    """Honour Retry-After when the server sends a sane one, else back off."""
    header = resp.headers.get("Retry-After", "").strip()
    if header.isdigit():
        return min(float(header), MAX_RETRY_WAIT_SECONDS)
    return RETRY_WAIT_SECONDS


def get(client: httpx.Client, url: str) -> httpx.Response:
    """GET with one polite retry on rate-limit responses."""
    resp = client.get(url)
    if resp.status_code in RETRY_STATUSES:
        wait = _retry_wait(resp)
        log.info("%s returned %d — retrying in %.0fs", url, resp.status_code, wait)
        time.sleep(wait)
        resp = client.get(url)
    return resp


def fetch_text(client: httpx.Client, url: str) -> str:
    resp = get(client, url)
    resp.raise_for_status()
    return resp.text


class ScrapeResult:
    """Per-source outcome, collected for the healthcheck report."""

    def __init__(self, source_id: str):
        self.source_id = source_id
        self.events: list[RawEvent] = []
        self.error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
