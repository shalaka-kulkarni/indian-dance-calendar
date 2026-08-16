"""Operator CLI. Publishing is automatic; these commands are for spot fixes:

  skyd report                          show the needs_attention queue
  skyd add --title .. --date .. --venue .. --url ..   hand-enter an event
  skyd tag <event-id> kathak,odissi    set curated forms
  skyd note <event-id> "text"          set the editor note
  skyd hide <event-id>                 force an event off the site
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from pipeline.models import (
    Curated,
    DanceForm,
    Event,
    Scraped,
    SourceRecord,
    Status,
)
from pipeline.normalize import infer_region, parse_price, parse_when
from pipeline.run import cmd_report
from pipeline.store import (
    EVENTS_DIR,
    content_hash,
    load_event,
    make_event_id,
    save_event,
)


def find_event_path(event_id: str) -> Path:
    matches = list(EVENTS_DIR.rglob(f"{event_id}*.yaml"))
    if len(matches) != 1:
        sys.exit(f"expected exactly one match for {event_id!r}, found {len(matches)}")
    return matches[0]


def cmd_add(args) -> None:
    start = parse_when(args.date)
    if start is None:
        sys.exit(f"could not parse date: {args.date!r}")
    price_min, price_max, is_free, note = parse_price(args.price or "")
    scraped = Scraped(
        title=args.title,
        start=start,
        venue=args.venue,
        region=infer_region(args.venue, args.address or ""),
        address=args.address or "",
        price_min=price_min,
        price_max=price_max,
        is_free=is_free,
        price_note=note,
        info_url=args.url,
        ticket_url=args.tickets or "",
        description_snippet=args.description or "",
        sources=[SourceRecord(source_id="manual", url=args.url, first_seen=date.today(), last_seen=date.today())],
    )
    scraped.content_hash = content_hash(scraped)
    event = Event(
        id=make_event_id(scraped),
        status=Status.NEEDS_ATTENTION,  # next sweep validates links and publishes
        needs_recheck=True,
        scraped=scraped,
        curated=Curated(forms=[DanceForm(f) for f in (args.forms or "").split(",") if f]),
    )
    path = save_event(event, human=True)
    print(f"added {path} — it will publish once the next sweep's checks pass")


def cmd_tag(args) -> None:
    event = load_event(find_event_path(args.event_id))
    event.curated.forms = [DanceForm(f.strip()) for f in args.forms.split(",") if f.strip()]
    save_event(event, human=True)
    print(f"tagged {event.id}: {[f.value for f in event.curated.forms]}")


def cmd_note(args) -> None:
    event = load_event(find_event_path(args.event_id))
    event.curated.editor_note = args.text
    save_event(event, human=True)
    print(f"noted {event.id}")


def cmd_hide(args) -> None:
    event = load_event(find_event_path(args.event_id))
    event.status = Status.REJECTED
    save_event(event, human=True)
    print(f"hidden {event.id} (status=rejected). Rebuild site data to update the site.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skyd")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("report")

    add = sub.add_parser("add")
    add.add_argument("--title", required=True)
    add.add_argument("--date", required=True, help='e.g. "Sep 19 2026 6pm"')
    add.add_argument("--venue", required=True)
    add.add_argument("--url", required=True, help="event info page")
    add.add_argument("--tickets", help="ticket purchase URL if separate")
    add.add_argument("--price", help='e.g. "$20-45", "Free", "from $25"')
    add.add_argument("--address")
    add.add_argument("--description")
    add.add_argument("--forms", help="comma-separated: kathak,odissi,...")

    tag = sub.add_parser("tag")
    tag.add_argument("event_id")
    tag.add_argument("forms")

    note = sub.add_parser("note")
    note.add_argument("event_id")
    note.add_argument("text")

    hide = sub.add_parser("hide")
    hide.add_argument("event_id")

    args = parser.parse_args(argv)
    if args.command == "report":
        cmd_report()
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "tag":
        cmd_tag(args)
    elif args.command == "note":
        cmd_note(args)
    elif args.command == "hide":
        cmd_hide(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
