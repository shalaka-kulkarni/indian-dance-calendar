"""The publish checker. Because publishing is automatic (no human gate), every
event must pass ALL of these before it appears on the site, and published
events get re-checked on every healthcheck run:

  1. links_live       — info_url (and ticket_url when present) answer with < 400
  2. has_info_url     — an information page exists
  3. date_valid       — parseable date, in the future (or currently running)
  4. in_metro         — venue/address resolves to the NYC-metro region
  5. classified       — Claude marked it relevant with medium+ confidence
                        (or the source is assume_relevant with any classification)

`price_known` is recorded but is NOT blocking: plenty of real listings (free
library lectures, programmes announced before tickets go on sale) never state a
price, and the site renders those honestly as "Price TBA" with a live link to
the venue. Withholding a real event over a missing price serves nobody.

A failure never deletes an event — it moves it to needs_attention with the
problem list attached, and the healthcheck surfaces the queue as a report.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

from pipeline.models import (
    Confidence,
    Event,
    LinkCheck,
    Region,
    Status,
    Validation,
)
from pipeline.scrapers.base import log

NY_TZ = ZoneInfo("America/New_York")
LINK_TIMEOUT = 20.0

# Checks that gate publication. price_known is deliberately absent — see module docstring.
BLOCKING_CHECKS = (
    "has_info_url",
    "specific_url",
    "links_live",
    "date_valid",
    "in_metro",
    "classified",
)


# Only these mean the page is genuinely gone. Big venue sites (Carnegie Hall,
# Asia Society, ticketing platforms) sit behind WAFs that answer automated
# requests with 403/405/429 while serving humans perfectly well, and 5xx is the
# server having a bad day. Treating any of those as "dead" deletes good
# listings, which is a worse failure than keeping a link we could not re-verify.
GONE_CODES = {404, 410}


def check_link(client: httpx.Client, url: str) -> LinkCheck:
    now = datetime.now(NY_TZ)
    try:
        resp = client.head(url, follow_redirects=True, timeout=LINK_TIMEOUT)
        # Many servers reject HEAD; retry those with GET before judging.
        if resp.status_code >= 400:
            resp = client.get(url, follow_redirects=True, timeout=LINK_TIMEOUT)
        return LinkCheck(
            url=url,
            ok=resp.status_code not in GONE_CODES,
            status_code=resp.status_code,
            checked_at=now,
        )
    except httpx.HTTPError as exc:
        # Could not reach it at all — that is a real failure.
        log.debug("link check failed %s: %s", url, exc)
        return LinkCheck(url=url, ok=False, status_code=None, checked_at=now)


def validate_event(
    event: Event,
    assume_relevant: bool = False,
    client: httpx.Client | None = None,
    check_links: bool = True,
    now: datetime | None = None,
) -> Validation:
    now = now or datetime.now(NY_TZ)
    scraped = event.scraped
    checks: dict[str, bool] = {}
    problems: list[str] = []
    link_checks: list[LinkCheck] = []

    checks["has_info_url"] = bool(scraped.info_url)
    if not checks["has_info_url"]:
        problems.append("no info URL")

    # A live link is not the same as a useful one. A bare homepage passes a
    # reachability check while telling the reader nothing about the event, so
    # the link must point somewhere deeper than the domain root.
    path = urlparse(scraped.info_url).path if scraped.info_url else ""
    checks["specific_url"] = len(path.strip("/")) > 0
    if not checks["specific_url"]:
        problems.append(f"info URL is a bare homepage, not an event page: {scraped.info_url}")

    if check_links and client is not None:
        urls = [u for u in {scraped.info_url, scraped.ticket_url} if u]
        link_checks = [check_link(client, u) for u in urls]
        checks["links_live"] = all(lc.ok for lc in link_checks) and bool(link_checks)
        if not checks["links_live"]:
            dead = [lc.url for lc in link_checks if not lc.ok]
            problems.append(f"dead links: {', '.join(dead) or 'none reachable'}")
    else:
        # Offline runs (tests, no-network environments) leave links unverified —
        # which counts as NOT passed, so nothing unverified goes live by accident.
        checks["links_live"] = False
        problems.append("links not yet verified (offline run)")

    last_date = max(
        [scraped.start, *(scraped.additional_dates or [])]
        + ([scraped.end] if scraped.end else [])
    )
    checks["date_valid"] = last_date >= now
    if not checks["date_valid"]:
        problems.append(f"event date {last_date.date()} is in the past")

    checks["price_known"] = (
        scraped.is_free or scraped.price_min is not None or bool(scraped.price_note)
    )
    if not checks["price_known"]:
        problems.append("no price information")

    checks["in_metro"] = scraped.region != Region.UNKNOWN
    if not checks["in_metro"]:
        problems.append("region unknown — can't confirm NYC metro")

    if event.ai is None:
        checks["classified"] = False
        problems.append("not yet classified (no API key run)")
    elif not event.ai.relevant:
        checks["classified"] = False
        problems.append("classified not-relevant")
    elif assume_relevant:
        checks["classified"] = True
    else:
        checks["classified"] = event.ai.confidence in (Confidence.HIGH, Confidence.MEDIUM)
        if not checks["classified"]:
            problems.append("relevance confidence too low for auto-publish")

    return Validation(
        passed=all(checks[name] for name in BLOCKING_CHECKS),
        checks=checks,
        link_checks=link_checks,
        problems=problems,
        validated_at=now,
    )


def validate_past_event(
    event: Event, client: httpx.Client | None = None, now: datetime | None = None
) -> Validation:
    """Archive events keep only the checks that still mean something: an info
    page that is still reachable. They carry no ticket link and their date is
    expected to be in the past."""
    now = now or datetime.now(NY_TZ)
    checks = {"has_info_url": bool(event.scraped.info_url)}
    problems: list[str] = [] if checks["has_info_url"] else ["no info URL"]
    link_checks: list[LinkCheck] = []
    if client is not None and event.scraped.info_url:
        link_checks = [check_link(client, event.scraped.info_url)]
        checks["links_live"] = link_checks[0].ok
        if not checks["links_live"]:
            problems.append(f"archive info link dead: {event.scraped.info_url}")
    elif event.validation and "links_live" in event.validation.checks:
        # Offline: carry forward the last real verdict rather than inventing one.
        checks["links_live"] = event.validation.checks["links_live"]
    # Otherwise leave links_live absent entirely — "not yet checked" must never
    # be recorded as "dead", which would silently empty the archive.
    return Validation(
        passed=all(checks.values()),
        checks=checks,
        link_checks=link_checks,
        problems=problems,
        validated_at=now,
    )


def apply_publish_policy(event: Event, validation: Validation) -> Status:
    """Decide the event's status from its validation. Rejected stays rejected
    (dedup memory); everything else is published iff validation passed."""
    event.validation = validation
    if event.ai is not None and not event.ai.relevant and event.ai.confidence == Confidence.HIGH:
        event.status = Status.REJECTED
    elif validation.passed:
        event.status = Status.PUBLISHED
        event.was_published = True
        event.needs_recheck = False
    else:
        event.status = Status.NEEDS_ATTENTION
    return event.status
