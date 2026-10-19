import pytest

from pipeline.textclean import clean_description, clean_title, clean_url, clean_venue

# Every case below is a title as a source actually published it.
FIXED = [
    # Organisers' misspellings of the city, on Sulekha.
    ("Dandiya Night With Garba Queen Foram Shah & Group In Niew York",
     "Dandiya Night with Garba Queen Foram Shah & Group in New York"),
    ("Mumbai Style Garba Ne Dandiya Night In Newyork",
     "Mumbai Style Garba Ne Dandiya Night in New York"),
    ("Bhakti Utsav Live With Sandeep Sehgal In Niewyork",
     "Bhakti Utsav Live with Sandeep Sehgal in New York"),
    # Acronyms flattened by Sulekha's capitalise-every-word filter.
    ("Once Upon A Time With Rahat Fateh Ali Khan & Shahzaman Ali Khan In Ny",
     "Once Upon a Time with Rahat Fateh Ali Khan & Shahzaman Ali Khan in NY"),
    ("Nye 2027 – New Year & New Beginnings With Dj Amrit In Ny",
     "NYE 2027 – New Year & New Beginnings with DJ Amrit in NY"),
    ("Ar Rahman Live In Concert", "A.R. Rahman Live in Concert"),
    # A search tag the arena appends to its page titles.
    ("Shreya Ghoshal: The Unstoppable Tour Tickets NJ", "Shreya Ghoshal: The Unstoppable Tour"),
    # CMANA writes initials without periods.
    ("2026 Flute J A Jayant", "2026 Flute J.A. Jayant"),
    ("2026 K S Vishnudev Fall Tour", "2026 K.S. Vishnudev Fall Tour"),
    # A spaced hyphen is a dash.
    ("Sitar Concert - Kalyan Majumdar", "Sitar Concert – Kalyan Majumdar"),
    # The first word after a dash or colon keeps its capital.
    ("Signed To God World Tour 2026 - A Sidhu Moose Wala Hologram Experience",
     "Signed to God World Tour 2026 – A Sidhu Moose Wala Hologram Experience"),
    # HTML codes and pictographs.
    ("Desi, Indian &amp; South Asian Singles - Speed Dating",
     "Desi, Indian & South Asian Singles – Speed Dating"),
    ("🎃11th Annual Spooktacular", "11th Annual Spooktacular"),
]

UNCHANGED = [
    # Editor-written titles: deliberate lower case, capitals and dashes stay.
    "Nrityagram Dance Ensemble: KHANKHANA",
    "Naad 2027: a festival of Indian music",
    "Rahat Fateh Ali Khan live in concert",
    "Holi Dance & Music Celebration: Festival of Colors",
    "Carved in Time — Mesma Belsare & Sonali Skandan",
    "FREE SUNDAY PERFORMING ARTS | Queens Outdoor Dance Festival | FALL 2026",
    "The Journey of Kuchipudi: From Yakshaganam to the Solo",
    # "Nye" is a surname unless a year or party follows.
    "Bill Nye Live",
]


@pytest.mark.parametrize("raw,expected", FIXED)
def test_clean_title_repairs_source_damage(raw, expected):
    assert clean_title(raw) == expected


@pytest.mark.parametrize("raw", UNCHANGED)
def test_clean_title_leaves_edited_titles_alone(raw):
    assert clean_title(raw) == raw


def test_clean_title_is_idempotent():
    for raw, _ in FIXED:
        once = clean_title(raw)
        assert clean_title(once) == once


def test_clean_venue():
    assert clean_venue("UBS Arena,") == "UBS Arena"
    assert clean_venue("Sapphire Banquet Ny") == "Sapphire Banquet NY"
    assert clean_venue("Tilles Center For The Performing Arts") == "Tilles Center for the Performing Arts"
    assert clean_venue("Bijou Nightclub &amp; Lounge") == "Bijou Nightclub & Lounge"


def test_clean_description_decodes_double_escaped_markup():
    raw = "&lt;p&gt;Join Ajna Dance Company for a fun &amp;amp; energetic evening&lt;/p&gt;"
    assert clean_description(raw) == "Join Ajna Dance Company for a fun & energetic evening"


def test_clean_url_repairs_doubled_scheme_and_drops_tracking():
    assert clean_url("http://https://swans.eventbrite.com/e/1") == "https://swans.eventbrite.com/e/1"
    assert (clean_url("https://tickets.irishartscenter.org/overview/3245?_ga=2.1065.17")
            == "https://tickets.irishartscenter.org/overview/3245")
    assert (clean_url("https://kupferbergcenter.org/event/wow/?gad_source=1&gad_campaignid=24258760736&gclid=x")
            == "https://kupferbergcenter.org/event/wow/")
    # Parameters that identify the event stay, untouched.
    assert clean_url("https://venue.org/show?id=42&utm_source=fb") == "https://venue.org/show?id=42"
    assert clean_url("https://venue.org/show?id=42&date=2026-10-15") == "https://venue.org/show?id=42&date=2026-10-15"


def test_clean_url_repairs_a_spaced_doubled_scheme():
    assert clean_url("http:// https://presenter.org/tickets") == "https://presenter.org/tickets"
    assert clean_url("https:// presenter.org/tickets") == "https://presenter.org/tickets"
    assert clean_url("https://presenter.org/fall show") == "https://presenter.org/fall%20show"
    # Two links run together: keep the last complete one.
    assert clean_url("https://presenter.org: https://tickets.org/show/1") == "https://tickets.org/show/1"
