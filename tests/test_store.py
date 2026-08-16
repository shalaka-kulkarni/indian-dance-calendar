from datetime import date

import pytest

from pipeline.models import Status
from pipeline.store import (
    CuratedWriteError,
    content_hash,
    expire_past_events,
    load_event,
    save_event,
)


def test_roundtrip(tmp_path, sample_event):
    path = save_event(sample_event, base=tmp_path)
    loaded = load_event(path)
    assert loaded == sample_event


def test_pipeline_cannot_touch_curated(tmp_path, sample_event):
    save_event(sample_event, base=tmp_path)
    sample_event.curated.editor_note = "sneaky pipeline edit"
    with pytest.raises(CuratedWriteError):
        save_event(sample_event, base=tmp_path)  # human=False is the default
    save_event(sample_event, base=tmp_path, human=True)  # humans may


def test_content_change_on_published_event_flags_recheck(tmp_path, sample_event):
    sample_event.status = Status.PUBLISHED
    save_event(sample_event, base=tmp_path)
    sample_event.scraped.price_max = 95.0  # venue silently raised prices
    sample_event.scraped.content_hash = content_hash(sample_event.scraped)
    save_event(sample_event, base=tmp_path)
    assert load_event(tmp_path / "2026" / f"{sample_event.id}.yaml").needs_recheck


def test_expire_past_events(tmp_path, sample_event):
    sample_event.status = Status.PUBLISHED
    save_event(sample_event, base=tmp_path)
    flipped = expire_past_events(base=tmp_path, today=date(2026, 12, 1))
    assert flipped == 1
    assert load_event(tmp_path / "2026" / f"{sample_event.id}.yaml").status == Status.PAST
    # Idempotent: second run flips nothing.
    assert expire_past_events(base=tmp_path, today=date(2026, 12, 1)) == 0


def test_expire_marks_past_and_preserves_was_published(tmp_path, sample_event):
    # Simulate a successful publish so the archive latch is set.
    sample_event.status = Status.PUBLISHED
    sample_event.was_published = True
    save_event(sample_event, base=tmp_path)
    expire_past_events(base=tmp_path, today=date(2026, 12, 1))
    reloaded = load_event(tmp_path / "2026" / f"{sample_event.id}.yaml")
    assert reloaded.status == Status.PAST
    assert reloaded.was_published is True
