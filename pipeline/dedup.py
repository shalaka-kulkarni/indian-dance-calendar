"""Cross-source deduplication.

Same event seen by two sources (e.g. The Joyce's own calendar AND The Dance
Enthusiast) must become ONE event that keeps BOTH source links — a
cross-circuit sighting is a signal worth showing, not noise.

Match rule: same date + (same venue OR either venue blank) + fuzzy title
match >= 85 (token_set_ratio, so "Nrityagram: KHANKHANA" matches
"Nrityagram Dance Ensemble — KHANKHANA").
"""

from __future__ import annotations

import re
from datetime import date

from rapidfuzz import fuzz

from pipeline.models import Event, Scraped
from pipeline.store import content_hash

TITLE_THRESHOLD = 85
VENUE_THRESHOLD = 80


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", text.lower()).split())


def same_event(a: Scraped, b: Scraped) -> bool:
    if a.start.date() != b.start.date():
        return False
    va, vb = _norm(a.venue), _norm(b.venue)
    if va and vb and fuzz.token_set_ratio(va, vb) < VENUE_THRESHOLD:
        return False
    return fuzz.token_set_ratio(_norm(a.title), _norm(b.title)) >= TITLE_THRESHOLD


def find_match(candidate: Scraped, existing: list[Event]) -> Event | None:
    # Fast path: same source URL already recorded.
    for event in existing:
        for record in event.scraped.sources:
            if record.url and record.url == candidate.sources[0].url:
                return event
    for event in existing:
        if same_event(candidate, event.scraped):
            return event
    return None


def merge_into(event: Event, candidate: Scraped, today: date) -> bool:
    """Merge a new sighting into an existing event. Returns True if scraped
    facts changed (caller decides on re-validation via store.save_event)."""
    changed = False
    known_ids = {r.source_id for r in event.scraped.sources}
    for record in candidate.sources:
        if record.source_id not in known_ids:
            event.scraped.sources.append(record)
            changed = True
        else:
            for existing_record in event.scraped.sources:
                if existing_record.source_id == record.source_id:
                    existing_record.last_seen = today
    # Fill gaps from the new sighting — never overwrite a present fact with an
    # absent one.
    fillable = [
        "end", "address", "price_min", "price_max", "price_note",
        "ticket_url", "description_snippet",
    ]
    for field in fillable:
        current = getattr(event.scraped, field)
        incoming = getattr(candidate, field)
        if (current in (None, "", [])) and incoming not in (None, "", []):
            setattr(event.scraped, field, incoming)
            changed = True
    if candidate.is_free and not event.scraped.is_free:
        event.scraped.is_free = True
        changed = True
    new_hash = content_hash(event.scraped)
    if new_hash != event.scraped.content_hash:
        event.scraped.content_hash = new_hash
        changed = True
    return changed
