from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pipeline import build as build_module
from pipeline.build import _counts, event_to_site, price_label
from pipeline.models import DanceForm, Region, Status

NY = ZoneInfo("America/New_York")


def test_price_label_variants(sample_event):
    assert price_label(sample_event) == "$17–$72"
    sample_event.scraped.price_min = sample_event.scraped.price_max = 25.0
    assert price_label(sample_event) == "$25"
    sample_event.scraped.is_free = True
    assert price_label(sample_event) == "Free"


def test_past_events_drop_ticket_link(sample_event):
    upcoming = event_to_site(sample_event)
    assert upcoming["ticketUrl"] == "https://tickets.joyce.org/nrityagram"
    archived = event_to_site(sample_event, include_tickets=False)
    assert archived["ticketUrl"] is None
    # The info link must survive into the archive.
    assert archived["infoUrl"] == "https://www.joyce.org/nrityagram"


def test_filter_counts_include_empty_options(sample_event):
    sample_event.curated.forms = [DanceForm.ODISSI]
    counts = _counts([event_to_site(sample_event)])
    forms = {f["value"]: f["count"] for f in counts["forms"]}
    regions = {r["value"]: r["count"] for r in counts["regions"]}
    # Every canonical option is present so the UI can grey out the empty ones.
    assert forms["odissi"] == 1
    assert forms["kathak"] == 0
    assert regions["manhattan"] == 1
    assert regions["new_jersey"] == 0
    assert Region.UNKNOWN.value not in regions


def test_archive_window_excludes_old_and_dead_links(tmp_path, sample_event, monkeypatch):
    from pipeline.models import Validation

    now = datetime.now(NY)
    monkeypatch.setattr(build_module, "load_all_events", lambda: events)
    monkeypatch.setattr(build_module, "SITE_DATA", tmp_path / "events.json")
    monkeypatch.setattr(build_module, "SITE_ICS", tmp_path / "calendar.ics")

    recent = sample_event.model_copy(deep=True)
    recent.id, recent.status, recent.was_published = "recent", Status.PAST, True
    recent.scraped.start = now - timedelta(days=30)

    ancient = sample_event.model_copy(deep=True)
    ancient.id, ancient.status, ancient.was_published = "ancient", Status.PAST, True
    ancient.scraped.start = now - timedelta(days=400)

    dead = sample_event.model_copy(deep=True)
    dead.id, dead.status, dead.was_published = "dead", Status.PAST, True
    dead.scraped.start = now - timedelta(days=10)
    dead.validation = Validation(passed=False, checks={"links_live": False})

    never_published = sample_event.model_copy(deep=True)
    never_published.id, never_published.status = "never", Status.PAST
    never_published.was_published = False
    never_published.scraped.start = now - timedelta(days=5)

    events = [recent, ancient, dead, never_published]
    result = build_module.build_site_data()
    assert result["past"] == 1
    import json

    payload = json.loads((tmp_path / "events.json").read_text())
    assert [e["id"] for e in payload["pastEvents"]] == ["recent"]
