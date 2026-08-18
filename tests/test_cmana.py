from pipeline.scrapers.html_sources import extract_cmana

# Shape taken from the live probe: the date sits in its own span, with a stray
# space before the comma and none after it.
LISTING = """
<html><body>
  <div class="event-card">
    <h3>Vocal Concert by Sikkil Gurucharan</h3>
    <span class="category-name">Event Date:Sunday Sep 6 ,2026</span>
    <p>Accompanied by violin and mridangam. Tickets $20 - $40.</p>
    <a href="/events/sikkil-gurucharan">Details</a>
  </div>
  <div class="event-card">
    <h3>C3 Festival Day 1</h3>
    <span class="category-name">Event Date:Saturday Oct 3 ,2026</span>
    <a href="/events/c3-day-1">Details</a>
  </div>
  <div class="sidebar">
    <span class="category-name">Membership renewal</span>
  </div>
</body></html>
"""


def test_cmana_reads_its_dated_spans():
    events = extract_cmana(LISTING, "cmana", "https://www.cmana.org/events/")
    assert [e.title for e in events] == [
        "Vocal Concert by Sikkil Gurucharan",
        "C3 Festival Day 1",
    ]
    assert events[0].start_raw == "Sep 6, 2026"
    assert events[1].start_raw == "Oct 3, 2026"
    assert events[0].info_url == "https://www.cmana.org/events/sikkil-gurucharan"
    assert events[0].price_raw == "$20 - $40"


def test_cmana_start_raw_parses_to_a_real_date():
    from pipeline.normalize import parse_when

    events = extract_cmana(LISTING, "cmana", "https://www.cmana.org/events/")
    parsed = parse_when(events[0].start_raw)
    assert parsed is not None
    assert (parsed.year, parsed.month, parsed.day) == (2026, 9, 6)


def test_cmana_prefers_structured_data_when_a_page_gains_it():
    html = """<html><body><script type="application/ld+json">
      {"@type":"Event","name":"Veena Recital","startDate":"2026-09-06T18:00",
       "url":"https://www.cmana.org/events/veena"}
    </script></body></html>"""
    events = extract_cmana(html, "cmana", "https://www.cmana.org/events/")
    assert [e.title for e in events] == ["Veena Recital"]


def test_cmana_returns_nothing_on_an_empty_page():
    assert extract_cmana("<html><body></body></html>", "cmana", "https://x.org/e/") == []
