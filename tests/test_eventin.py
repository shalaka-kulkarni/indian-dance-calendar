from pipeline.scrapers.html_sources import extract_eventin

# Markup copied from a live probe of cmana.org/events.
LISTING = """
<html><body>
<div class="etn-event-item">
  <div class="etn-event-thumb">
    <a href="https://www.cmana.org/etn/2026-flute-j-a-jayant/"><img alt="Membership Form"/></a>
  </div>
  <div class="etn-event-content">
    <div class="etn-title-info">
      <h3 class="etn-title etn-event-title">
        <a href="https://www.cmana.org/etn/2026-flute-j-a-jayant/"> 2026 Flute J A Jayant</a>
      </h3>
      <p>Carnatic Flute Concert Flute J A Jayant Flute Support B Sreeram</p>
      <div class="etn-event-location">
        <i class="etn-icon etn-location"></i>
        Theater, Community Middle School. 95 Grovers Mill Road, Plainsboro NJ 08536
      </div>
    </div>
    <div class="etn-event-date">
      <span><i class="etn-icon etn-calendar"></i> October 3, 2026 </span>
    </div>
  </div>
</div>
<div class="etn-event-item">
  <div class="etn-event-content">
    <div class="etn-title-info">
      <h3 class="etn-title etn-event-title"><a href="/etn/vocal-sikkil/">Vocal: Sikkil Gurucharan</a></h3>
    </div>
    <div class="etn-event-date"><span> September 20, 2026 </span></div>
  </div>
</div>
<div class="etn-event-item">
  <div class="etn-title-info"><h3 class="etn-title"><a href="/etn/tbd/">Season TBD</a></h3></div>
</div>
</body></html>
"""


def test_eventin_reads_the_listing():
    events = extract_eventin(LISTING, "cmana", "https://www.cmana.org/events/")
    # The third item carries no date and must not become an event.
    assert [e.title for e in events] == ["2026 Flute J A Jayant", "Vocal: Sikkil Gurucharan"]

    flute = events[0]
    assert flute.start_raw == "October 3, 2026"
    assert flute.info_url == "https://www.cmana.org/etn/2026-flute-j-a-jayant/"
    assert "Plainsboro NJ" in flute.address
    assert "Carnatic Flute Concert" in flute.description
    # Relative hrefs resolve against the listing page.
    assert events[1].info_url == "https://www.cmana.org/etn/vocal-sikkil/"


def test_eventin_dates_parse_and_land_in_new_jersey():
    from pipeline.models import Region
    from pipeline.normalize import normalize

    events = extract_eventin(LISTING, "cmana", "https://www.cmana.org/events/")
    scraped = normalize(events[0])
    assert scraped is not None
    assert (scraped.start.year, scraped.start.month, scraped.start.day) == (2026, 10, 3)
    assert scraped.region is Region.NEW_JERSEY


def test_eventin_prefers_structured_data_when_a_page_gains_it():
    html = """<html><body><script type="application/ld+json">
      {"@type":"Event","name":"Veena Recital","startDate":"2026-09-06T18:00",
       "url":"https://www.cmana.org/etn/veena"}
    </script><div class="etn-event-item"></div></body></html>"""
    assert [e.title for e in extract_eventin(html, "cmana", "https://x.org/e/")] == ["Veena Recital"]


def test_eventin_returns_nothing_for_a_site_without_the_plugin():
    assert extract_eventin("<html><body><div class='x'></div></body></html>", "c", "https://x.org/e/") == []
