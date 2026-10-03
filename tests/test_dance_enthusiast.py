from pipeline.scrapers.html_sources import extract_dance_enthusiast

# Shape taken from a live probe on 3 Oct 2026.
PAGE = """
<div class="col_1110">
  <div id="event_date_selection"><h2 align="center">October 18-November 1, 2026</h2></div>
  <h2 class="date_col_heading highlight_fg">Sunday October 18, 2026</h2>
  <div class="col_100"><div>
    <a class="listing_container" href="/dance-listings/events/view/SAN-FRANCISCO-CA-Smuin-202627-Season-2026-10-09_18">
      <div class="image_small_container"><img alt="SAN FRANCISCO, CA: Smuin 2026/27 Season" class="image_small" src="/x.jpg"/>
      <div class="imageTitleB"><h2>SAN FRANCISCO, CA: Smuin 2026/27 Season</h2></div></div>
    </a>
    <a class="listing_container" href="/dance-listings/events/view/New-York-International-Dance-Festival-2026-10-18">
      <div class="image_small_container"><img alt="New York International Dance Festival" class="image_small" src="/y.jpg"/>
      <div class="imageTitleB"><h2>New York International Dance Festival</h2></div></div>
      <p>Bharatanatyam, Odissi, Flamenco and more at MMAC. Tickets $25</p>
    </a>
    <a class="listing_container" href="/dance-listings/events/view/The-Journey-of-Kuchipudi-2026-10-18">
      <div class="imageTitleB"><h2>The Journey of Kuchipudi: From Yakshaganam to the Solo</h2></div>
      <div class="listing_venue">Danspace Project</div>
      <div class="listing_when">Sun. October, 18 @ 7:30pm</div>
    </a>
    <a class="listing_container" href="/dance-listings/events/view/BUFFALO-NY-Nutcracker-2026-10-18">
      <div class="imageTitleB"><h2>BUFFALO, NY: Nutcracker</h2></div>
    </a>
  </div></div>
  <h2 class="date_col_heading highlight_fg">Monday October 19, 2026</h2>
  <div class="col_100"><div>
    <a class="listing_container" href="/dance-listings/events/view/JERSEY-CITY-NJ-Navratri-Garba-2026-10-19">
      <div class="imageTitleB"><h2>JERSEY CITY, NJ: Navratri Garba</h2></div>
    </a>
    <a class="listing_container" href="/dance-listings/events/view/New-York-International-Dance-Festival-2026-10-18">
      <div class="imageTitleB"><h2>New York International Dance Festival</h2></div>
    </a>
  </div></div>
</div>
"""


def test_dance_enthusiast_reads_day_headings_and_cards():
    events = extract_dance_enthusiast(PAGE, "dance_enthusiast", "https://www.dance-enthusiast.com/dance-listings/events")
    titles = [e.title for e in events]
    # Out-of-town prefixes are dropped; metro prefixes are stripped and kept.
    assert "New York International Dance Festival" in titles
    assert "Navratri Garba" in titles
    assert not any("Smuin" in t or "Nutcracker" in t for t in titles)
    # A listing repeated on a later day is one event, dated by its first heading.
    assert titles.count("New York International Dance Festival") == 1
    fest = next(e for e in events if e.title.startswith("New York International"))
    assert fest.start_raw == "October 18, 2026"
    assert fest.info_url.endswith("/view/New-York-International-Dance-Festival-2026-10-18")
    assert fest.price_raw == "$25"
    garba = next(e for e in events if e.title == "Navratri Garba")
    assert garba.start_raw == "October 19, 2026"


def test_dance_enthusiast_dates_parse():
    from pipeline.normalize import parse_when
    events = extract_dance_enthusiast(PAGE, "dance_enthusiast", "https://www.dance-enthusiast.com/dance-listings/events")
    d = parse_when(events[0].start_raw)
    assert d is not None and (d.year, d.month, d.day) == (2026, 10, 18)


def test_dance_enthusiast_empty_page():
    assert extract_dance_enthusiast("<html><body></body></html>", "dance_enthusiast", "https://x/") == []


def test_dance_enthusiast_reads_venue_and_clock_time_from_the_card():
    from pipeline.models import Region
    from pipeline.normalize import normalize
    events = extract_dance_enthusiast(PAGE, "dance_enthusiast", "https://www.dance-enthusiast.com/dance-listings/events")
    kuchipudi = next(e for e in events if e.title.startswith("The Journey of Kuchipudi"))
    assert kuchipudi.venue == "Danspace Project"
    assert kuchipudi.start_raw == "October 18, 2026 7:30pm"
    scraped = normalize(kuchipudi)
    assert (scraped.start.hour, scraped.start.minute) == (19, 30)
    # The venue name alone places it.
    assert scraped.region == Region.MANHATTAN
    # A card with no venue or time line still yields the event, dated by the heading.
    fest = next(e for e in events if e.title.startswith("New York International"))
    assert fest.venue == "" and fest.start_raw == "October 18, 2026"
    # Out-of-town prefixes that are kept become the address, so the region resolves.
    garba = next(e for e in events if e.title == "Navratri Garba")
    assert garba.address == "Jersey City, NJ"
    assert normalize(garba).region == Region.NEW_JERSEY
