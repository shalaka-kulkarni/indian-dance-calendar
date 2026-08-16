from datetime import date, datetime
from zoneinfo import ZoneInfo

from pipeline.dedup import find_match, merge_into, same_event
from pipeline.models import Scraped, SourceRecord
from pipeline.store import content_hash

NY = ZoneInfo("America/New_York")


def scraped(title: str, venue: str = "The Joyce Theater", source_id: str = "joyce", url: str = "https://a.org/x", **kw) -> Scraped:
    s = Scraped(
        title=title,
        start=kw.pop("start", datetime(2026, 10, 13, 19, 30, tzinfo=NY)),
        venue=venue,
        info_url=url,
        sources=[SourceRecord(source_id=source_id, url=url, first_seen=date(2026, 8, 1), last_seen=date(2026, 8, 1))],
        **kw,
    )
    s.content_hash = content_hash(s)
    return s


def test_same_event_fuzzy_title():
    a = scraped("Nrityagram: KHANKHANA")
    b = scraped("Nrityagram Dance Ensemble — KHANKHANA")
    assert same_event(a, b)


def test_different_dates_never_match():
    a = scraped("KHANKHANA")
    b = scraped("KHANKHANA", start=datetime(2026, 10, 14, 19, 30, tzinfo=NY))
    assert not same_event(a, b)


def test_different_shows_same_venue_do_not_match():
    a = scraped("Nrityagram: KHANKHANA")
    b = scraped("Ragamala: Fires of Varanasi")
    assert not same_event(a, b)


def test_merge_keeps_both_sources_and_fills_gaps(sample_event):
    # Cross-circuit sighting: Dance Enthusiast lists the same show with an address.
    sighting = scraped(
        "Nrityagram Dance Ensemble KHANKHANA",
        source_id="dance_enthusiast",
        url="https://www.dance-enthusiast.com/x",
        address="175 8th Ave, New York",
    )
    changed = merge_into(sample_event, sighting, date(2026, 8, 10))
    assert changed
    ids = {r.source_id for r in sample_event.scraped.sources}
    assert ids == {"joyce", "dance_enthusiast"}
    assert sample_event.scraped.address == "175 8th Ave, New York"
    # Present facts are never overwritten by absent ones.
    assert sample_event.scraped.price_min == 17.0


def test_find_match_by_source_url(sample_event):
    resight = scraped("Totally Renamed Listing", url="https://www.joyce.org/nrityagram")
    assert find_match(resight, [sample_event]) is sample_event
