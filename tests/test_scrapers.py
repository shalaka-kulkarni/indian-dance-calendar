from pipeline.scrapers.html_sources import extract_listing_blocks, extract_narthaki
from pipeline.scrapers.ics import extract_ics_events
from pipeline.scrapers.jsonld import extract_jsonld_events
from tests.conftest import fixture_text

PAGE = "https://example-venue.org/calendar"


def test_jsonld_extracts_all_events_with_offers():
    events = extract_jsonld_events(fixture_text("venue_jsonld.html"), "joyce", PAGE)
    assert len(events) == 2
    ragamala = events[0]
    assert ragamala.title == "Ragamala Dance Company: Fires of Varanasi"
    assert ragamala.start_raw == "2026-09-18T19:30:00-04:00"
    assert ragamala.venue == "Example Venue Theater"
    assert "175 8th Ave" in ragamala.address
    assert ragamala.price_raw == "12-72"
    assert ragamala.info_url == "https://example-venue.org/events/ragamala"
    assert ragamala.ticket_url == "https://example-venue.org/tickets/ragamala"


def test_jsonld_no_keyword_prefilter():
    # The non-Indian chamber music event must ALSO come through — filtering is
    # classification's job, never the scraper's.
    events = extract_jsonld_events(fixture_text("venue_jsonld.html"), "joyce", PAGE)
    titles = {e.title for e in events}
    assert "An Evening of Chamber Music" in titles


def test_ics_extraction():
    events = extract_ics_events(fixture_text("feed.ics"), "flushing_town_hall", "https://example.org/feed.ics")
    assert len(events) == 1
    ev = events[0]
    assert ev.title == "Diwali Folk Dance Celebration"
    assert ev.start_raw.startswith("2026-10-24T19:00:00")
    assert "Flushing" in ev.venue
    assert ev.info_url == "https://example.org/diwali"


def test_narthaki_keeps_only_ny_metro():
    events = extract_narthaki(fixture_text("narthaki_like.html"), "narthaki", "https://narthaki.com/info/fevents.html")
    joined = " ".join(e.title for e in events)
    assert "Erasing Borders" in joined
    assert "Carved in Time" in joined
    assert "Pittsburgh" not in joined
    # Relative links resolve against the page URL.
    erasing = next(e for e in events if "Erasing Borders" in e.title)
    assert erasing.info_url == "https://narthaki.com/events/erasing-borders-2026.html"


def test_listing_blocks_fallback_requires_date_and_link():
    events = extract_listing_blocks(fixture_text("listing_blocks.html"), "laguardia_pac", "https://example.org/events")
    titles = {e.title for e in events}
    assert "Kathak Night: Tarini Tripathi" in titles
    assert "Jazz Quartet in Residence" in titles  # no pre-filtering here either
    assert "Season Announcement" not in titles  # no date -> not an event yet
    kathak = next(e for e in events if "Kathak" in e.title)
    assert kathak.price_raw.startswith("$25")
    assert kathak.info_url == "https://example.org/events/kathak-night"
