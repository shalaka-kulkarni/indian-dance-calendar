from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pipeline import build as build_module
from pipeline.build import _counts, event_to_site, price_label
from pipeline.models import ArtForm, DanceForm, Region, Status, Tradition

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
    sample_event.curated.traditions = [Tradition.CLASSICAL]
    counts = _counts([event_to_site(sample_event)])
    traditions = {t["value"]: t["count"] for t in counts["traditions"]}
    regions = {r["value"]: r["count"] for r in counts["regions"]}
    # Every canonical option is present so the UI can grey out the empty ones.
    assert traditions["classical"] == 1
    assert traditions["folk"] == 0
    assert regions["manhattan"] == 1
    assert regions["new_jersey"] == 0
    assert Region.UNKNOWN.value not in regions


def test_each_art_form_counts_only_under_its_own_chip(sample_event):
    """"Dance" has to mean dance. A "both" event counts under Both, not under
    Dance and Music as well — otherwise filtering to Dance returns concerts."""
    sample_event.curated.art_form = ArtForm.BOTH
    sample_event.curated.traditions = [Tradition.FOLK]
    counts = _counts([event_to_site(sample_event)])
    art = {a["value"]: a["count"] for a in counts["artForms"]}
    assert art.get("both") == 1
    assert not art.get("dance")
    assert not art.get("music")


def test_ticket_link_identical_to_info_is_dropped(sample_event):
    """One destination should render as one button, not two that go to the same page."""
    sample_event.scraped.ticket_url = sample_event.scraped.info_url
    assert event_to_site(sample_event)["ticketUrl"] is None


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
