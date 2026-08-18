"""Pipeline orchestrator.

  python -m pipeline.run sweep      # scrape registry + platforms -> classify -> validate -> save
  python -m pipeline.run discover   # broad search battery -> same funnel
  python -m pipeline.run classify   # (re)classify events missing classification
  python -m pipeline.run validate   # re-run the publish checker on everything live
  python -m pipeline.run build      # emit site data + ICS
  python -m pipeline.run report     # print needs_attention queue + source health
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from pipeline import build as site_build
from pipeline.classify import classify_event
from pipeline.dedup import find_match, merge_into
from pipeline.discovery import run_discovery
from pipeline.models import Event, Region, Source, Status, Strategy
from pipeline.normalize import normalize
from pipeline.registry import load_sources
from pipeline.scrapers.base import RawEvent, ScrapeResult, fetch_text, log, make_client
from pipeline.scrapers.crawl import deep_extract
from pipeline.scrapers.html_sources import (
    extract_eventin,
    extract_listing_blocks,
    extract_narthaki,
)
from pipeline.scrapers.ics import extract_ics_events
from pipeline.scrapers.platforms import eventbrite_events, ticketmaster_events
from pipeline.scrapers.sitemap import sitemap_extract
from pipeline.scrapers.tribe import tribe_events
from pipeline.store import (
    expire_past_events,
    load_all_events,
    make_event_id,
    save_event,
)
from pipeline.validate import apply_publish_policy, validate_event, validate_past_event

NY_TZ = ZoneInfo("America/New_York")
HEALTH_PATH = Path(__file__).resolve().parent.parent / "out" / "source_health.json"

BESPOKE = {
    "narthaki": extract_narthaki,
    "cmana": extract_eventin,
}


def scrape_source(client: httpx.Client, source: Source) -> ScrapeResult:
    result = ScrapeResult(source.id)
    try:
        if source.strategy == Strategy.API:
            if source.id == "eventbrite":
                result.events = eventbrite_events(client)
            elif source.id == "ticketmaster":
                result.events = ticketmaster_events(client)
        elif source.strategy == Strategy.ICS:
            result.events = extract_ics_events(fetch_text(client, source.url), source.id, source.url)
        elif source.strategy in (Strategy.JSONLD, Strategy.HTML):
            html = fetch_text(client, source.url)
            extractor = BESPOKE.get(source.id)
            if extractor:
                result.events = extractor(html, source.id, source.url)
            else:
                result.events = extract_listing_blocks(html, source.id, source.url)
            # JS-rendered listing pages yield nothing here, but their event
            # detail pages usually carry JSON-LD — follow links and extract.
            if not result.events:
                result.events = deep_extract(client, source.id, source.url, html)
            # Client-side calendars expose no links at all; the sitemap still
            # lists every event page for search engines.
            if not result.events:
                result.events = sitemap_extract(client, source.id, source.url)
            # WordPress venues whose detail pages carry no JSON-LD defeat all of
            # the above even though every page fetches fine. Their plugin's API
            # does not.
            if not result.events:
                result.events = tribe_events(client, source.id, source.url)
    except Exception as exc:  # noqa: BLE001 — isolation: one source never sinks the sweep
        result.error = f"{type(exc).__name__}: {exc}"
        log.warning("source %s failed: %s", source.id, result.error)
    return result


def ingest(raw_events: list[RawEvent], sources_by_id: dict[str, Source], client: httpx.Client | None, check_links: bool) -> dict:
    """The shared funnel: normalize -> dedup -> classify -> validate -> save."""
    today = date.today()
    existing = load_all_events()
    stats = {"new": 0, "updated": 0, "published": 0, "needs_attention": 0, "rejected": 0, "skipped": 0}
    for raw in raw_events:
        source = sources_by_id.get(raw.source_id)
        scraped = normalize(raw, source.region if source else Region.UNKNOWN, today)
        if scraped is None:
            stats["skipped"] += 1
            continue
        # Skip events already in the past at ingest time.
        if scraped.start < datetime.now(NY_TZ):
            stats["skipped"] += 1
            continue
        match = find_match(scraped, existing)
        assume = source.assume_relevant if source else False
        if match is None:
            event = Event(id=make_event_id(scraped), status=Status.NEEDS_ATTENTION, scraped=scraped)
            existing.append(event)
            stats["new"] += 1
        else:
            event = match
            if merge_into(event, scraped, today):
                stats["updated"] += 1
        if event.ai is None or event.needs_recheck:
            classification = classify_event(
                event.scraped,
                source.name if source else raw.source_id,
                source.circuit.value if source else "unknown",
                assume_relevant=assume,
            )
            if classification is not None:
                event.ai = classification
        validation = validate_event(event, assume_relevant=assume, client=client, check_links=check_links)
        status = apply_publish_policy(event, validation)
        stats[status.value] = stats.get(status.value, 0) + 1
        save_event(event)
    return stats


def cmd_sweep(check_links: bool = True) -> dict:
    client = make_client()
    sources = load_sources()
    sources_by_id = {s.id: s for s in sources}
    results: list[ScrapeResult] = []
    raw_events: list[RawEvent] = []
    for source in sources:
        if source.strategy in (Strategy.SEARCH, Strategy.MANUAL):
            continue
        result = scrape_source(client, source)
        results.append(result)
        raw_events.extend(result.events)
    stats = ingest(raw_events, sources_by_id, client, check_links)
    expired = expire_past_events()
    stats["expired"] = expired
    health = {
        r.source_id: {"ok": r.ok, "events": len(r.events), "error": r.error} for r in results
    }
    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_PATH.write_text(json.dumps({"ran_at": datetime.now(NY_TZ).isoformat(), "sources": health}, indent=1))
    log.info("sweep: %s", stats)
    return stats


def cmd_discover() -> dict:
    client = make_client()
    sources_by_id = {s.id: s for s in load_sources(enabled_only=False)}
    raw_events, host_yield = run_discovery(client)
    stats = ingest(raw_events, sources_by_id, client, check_links=True)
    if host_yield:
        proposals = Path(__file__).resolve().parent.parent / "out" / "proposed_sources.json"
        proposals.parent.mkdir(parents=True, exist_ok=True)
        proposals.write_text(json.dumps(host_yield, indent=1))
        log.info("discovery: proposed new source hosts: %s", host_yield)
    stats["proposed_hosts"] = len(host_yield)
    return stats


def cmd_classify() -> dict:
    sources_by_id = {s.id: s for s in load_sources(enabled_only=False)}
    count = 0
    for event in load_all_events():
        if event.ai is not None or event.status in (Status.PAST, Status.REJECTED):
            continue
        first_source = event.scraped.sources[0].source_id if event.scraped.sources else ""
        source = sources_by_id.get(first_source)
        classification = classify_event(
            event.scraped,
            source.name if source else first_source,
            source.circuit.value if source else "unknown",
            assume_relevant=source.assume_relevant if source else False,
        )
        if classification is not None:
            event.ai = classification
            save_event(event)
            count += 1
    return {"classified": count}


def cmd_validate(check_links: bool = True) -> dict:
    client = make_client() if check_links else None
    sources_by_id = {s.id: s for s in load_sources(enabled_only=False)}
    stats = {"published": 0, "needs_attention": 0, "rejected": 0}
    for event in load_all_events():
        if event.status == Status.PAST:
            # Archive entries: re-check the info link so the past-events page
            # never shows a dead link. Status stays PAST either way.
            if event.was_published:
                event.validation = validate_past_event(event, client=client)
                save_event(event)
            continue
        # Offline runs can't verify links; never let that demote a live event.
        if not check_links and event.status == Status.PUBLISHED:
            continue
        first_source = event.scraped.sources[0].source_id if event.scraped.sources else ""
        source = sources_by_id.get(first_source)
        assume = source.assume_relevant if source else False
        validation = validate_event(event, assume_relevant=assume, client=client, check_links=check_links)
        status = apply_publish_policy(event, validation)
        stats[status.value] = stats.get(status.value, 0) + 1
        save_event(event)
    expire_past_events()
    return stats


def cmd_report() -> dict:
    events = load_all_events()
    queue = [e for e in events if e.status == Status.NEEDS_ATTENTION]
    print(f"\n=== needs_attention queue ({len(queue)}) ===")
    for event in sorted(queue, key=lambda e: e.scraped.start):
        problems = event.validation.problems if event.validation else ["never validated"]
        print(f"- {event.scraped.start.date()} {event.scraped.title[:70]}")
        print(f"    {'; '.join(problems)}")
    published = [e for e in events if e.status == Status.PUBLISHED]
    print(f"\n=== published: {len(published)} | past: {sum(1 for e in events if e.status == Status.PAST)} | rejected: {sum(1 for e in events if e.status == Status.REJECTED)} ===")
    return {"needs_attention": len(queue), "published": len(published)}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="pipeline.run")
    parser.add_argument(
        "command",
        choices=["sweep", "discover", "classify", "validate", "build", "report", "probe"],
    )
    parser.add_argument("--no-link-check", action="store_true", help="skip network link verification (offline runs)")
    parser.add_argument("targets", nargs="*", help="probe: source ids or URLs to diagnose")
    args = parser.parse_args(argv)
    if args.command == "sweep":
        print(json.dumps(cmd_sweep(check_links=not args.no_link_check)))
    elif args.command == "discover":
        print(json.dumps(cmd_discover()))
    elif args.command == "classify":
        print(json.dumps(cmd_classify()))
    elif args.command == "validate":
        print(json.dumps(cmd_validate(check_links=not args.no_link_check)))
    elif args.command == "build":
        print(json.dumps(site_build.build_site_data()))
    elif args.command == "report":
        cmd_report()
    elif args.command == "probe":
        from pipeline.probe import probe_sources

        if not args.targets:
            parser.error("probe needs at least one source id or URL")
        probe_sources(args.targets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
