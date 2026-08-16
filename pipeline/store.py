"""Read/write event YAML files with ownership-zone enforcement.

Rules this module enforces:
  * The pipeline may freely rewrite `scraped`, `ai`, and `validation`.
  * The pipeline may NEVER write `curated` — save_event() refuses any change to
    it unless the caller passes human=True (used only by the CLI / a human).
  * When a re-scrape changes the content of an already-published event
    (date moved, cancelled, price change), the event gets needs_recheck=True
    and is re-validated before it stays on the site.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from pipeline.models import Event, Scraped, Status

NY_TZ = ZoneInfo("America/New_York")
EVENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "events"


class CuratedWriteError(Exception):
    """Raised when non-human code attempts to modify the curated zone."""


def content_hash(scraped: Scraped) -> str:
    """Hash of the facts that matter for change detection."""
    parts = [
        scraped.title.strip().lower(),
        scraped.start.isoformat(),
        scraped.end.isoformat() if scraped.end else "",
        "|".join(sorted(d.isoformat() for d in scraped.additional_dates)),
        scraped.venue.strip().lower(),
        str(scraped.price_min),
        str(scraped.price_max),
        str(scraped.is_free),
        scraped.info_url,
        scraped.ticket_url,
    ]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


def slugify(text: str, max_words: int = 5) -> str:
    words = re.sub(r"[^a-z0-9\s-]", "", text.lower()).split()
    return "-".join(words[:max_words])


def make_event_id(scraped: Scraped) -> str:
    return f"{scraped.start.date().isoformat()}-{slugify(scraped.venue, 2)}-{slugify(scraped.title, 4)}"


def event_path(event_id: str, base: Path | None = None) -> Path:
    year = event_id[:4]
    return (base or EVENTS_DIR) / year / f"{event_id}.yaml"


def load_event(path: Path) -> Event:
    with open(path) as f:
        return Event.model_validate(yaml.safe_load(f))


def load_all_events(base: Path | None = None) -> list[Event]:
    base = base or EVENTS_DIR
    if not base.exists():
        return []
    return [load_event(p) for p in sorted(base.rglob("*.yaml"))]


def save_event(event: Event, base: Path | None = None, human: bool = False) -> Path:
    """Persist an event, enforcing the curated-zone write barrier."""
    path = event_path(event.id, base)
    if path.exists() and not human:
        existing = load_event(path)
        if existing.curated != event.curated:
            raise CuratedWriteError(
                f"pipeline attempted to modify curated zone of {event.id}"
            )
        # A content change on a live event demands re-validation before it stays up.
        if (
            existing.status == Status.PUBLISHED
            and existing.scraped.content_hash
            and event.scraped.content_hash != existing.scraped.content_hash
        ):
            event.needs_recheck = True
    path.parent.mkdir(parents=True, exist_ok=True)
    data = event.model_dump(mode="json", exclude_none=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=100)
    return path


def expire_past_events(base: Path | None = None, today: date | None = None) -> int:
    """Flip published events whose last date has passed to PAST. Returns count."""
    today = today or datetime.now(NY_TZ).date()
    flipped = 0
    for event in load_all_events(base):
        if event.status not in (Status.PUBLISHED, Status.NEEDS_ATTENTION):
            continue
        last = max(
            [event.scraped.start, *(event.scraped.additional_dates or [])]
            + ([event.scraped.end] if event.scraped.end else [])
        )
        if last.date() < today:
            event.status = Status.PAST
            save_event(event, base)
            flipped += 1
    return flipped
