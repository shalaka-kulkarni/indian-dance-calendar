"""Shared scraping plumbing: polite fetching, the RawEvent intermediate shape,
and per-source error isolation so one broken source never sinks a sweep."""

from __future__ import annotations

import logging
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

DEFAULT_TIMEOUT = 30.0


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
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en"},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )


def fetch_text(client: httpx.Client, url: str) -> str:
    resp = client.get(url)
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
