from pipeline.scrapers.html_sources import extract_gibney

# Shape taken from a live probe of gibneydance.org/calendar/ on 3 Oct 2026.
PAGE = r"""
<html><body><main class="entry-content" id="page-wrapper">
<script> var eventDates = [{"start":"2026-12-02","title":"Antonin Rioche Repertoire Workshop with \u00c8ve-Marie Dalcourt","url":"https:\/\/gibneydance.org\/event\/antonin-rioche-repertoire-workshop\/","target":"_self","excerpt":"About the Workshop","print_start_time":"10:00 am","print_end_time":"2:00 pm","image":"https:\/\/gibneydance.org\/x.jpg","alt_text":"","end":"2026-12-02","print_end_date":"Dec 2, 2026"},{"start":"2026-11-14","title":"Carved in Time","url":"https:\/\/gibneydance.org\/event\/carved-in-time\/","target":"_self","excerpt":"Bharatanatyam by Sonali Skandan and Mesma Belsar\u00e9","print_start_time":"7:00 pm","print_end_time":"9:00 pm","image":"","alt_text":"","end":"2026-11-14","print_end_date":"Nov 14, 2026"},{"start":"2026-10-05","title":"Lucinda Childs Repertory Workshop","url":"https:\/\/gibneydance.org\/event\/lucinda-childs\/","print_start_time":"10:00 am","print_end_time":"3:00 pm","end":"2026-10-08"}]; </script>
<div><span>Oct 5, 2026 </span><h3>Lucinda Childs Repertory Workshop: Concerto</h3></div>
</main></body></html>
"""


def test_gibney_reads_the_inline_event_array():
    events = extract_gibney(PAGE, "gibney", "https://gibneydance.org/calendar/")
    assert [e.title for e in events] == [
        "Antonin Rioche Repertoire Workshop with Ève-Marie Dalcourt",
        "Carved in Time",
        "Lucinda Childs Repertory Workshop",
    ]
    carved = events[1]
    assert carved.start_raw == "2026-11-14 7:00 pm"
    assert carved.end_raw == ""  # same-day end adds nothing
    assert carved.info_url == "https://gibneydance.org/event/carved-in-time/"
    assert carved.venue == "Gibney"
    assert "Bharatanatyam" in carved.description
    # A multi-day run keeps its end.
    assert events[2].end_raw == "2026-10-08 3:00 pm"


def test_gibney_dates_normalize():
    from pipeline.models import Region
    from pipeline.normalize import normalize
    events = extract_gibney(PAGE, "gibney", "https://gibneydance.org/calendar/")
    scraped = normalize(events[1], Region.MANHATTAN)
    assert (scraped.start.month, scraped.start.day, scraped.start.hour) == (11, 14, 19)
    assert scraped.region == Region.MANHATTAN


def test_gibney_without_the_array_yields_nothing():
    assert extract_gibney("<html><body><p>Calendar</p></body></html>", "gibney", "https://gibneydance.org/calendar/") == []
