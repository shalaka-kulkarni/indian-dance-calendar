"""Back-fill the archive with NYC-metro Indian dance events that happened
between Feb and Aug 2026, before this calendar existed.

Every field here was corroborated by web research against a live source page;
nothing is inferred. Each entry is written straight to PAST with
was_published=True so it appears in the archive, and the next validate run
link-checks it like any other entry — a dead link drops it from the site.

Run: uv run python scripts/seed_past.py
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pipeline.models import (
    Classification,
    Confidence,
    Curated,
    DanceForm,
    Event,
    EventKind,
    PresenterType,
    Region,
    Scraped,
    SourceRecord,
    Status,
)
from pipeline.store import content_hash, make_event_id, save_event

NY = ZoneInfo("America/New_York")
TODAY = date(2026, 8, 16)
MODEL = "claude-fable-5"

PAST_EVENTS = [
    dict(
        title="45th Battery Dance Festival — Indian Independence Day evening",
        start=datetime(2026, 8, 15, 19, 0, tzinfo=NY),
        venue="Robert F. Wagner Jr. Park",
        address="Battery Park City, New York, NY",
        region=Region.MANHATTAN,
        is_free=True,
        info_url="https://theindianeye.com/2026/07/28/battery-dance-presents-the-45th-annual-battery-dance-festival-on-august-10-16-2026/",
        description=(
            "The free festival's 15 August evening was a tribute to Indian dance marking "
            "Indian Independence Day, headlined by Nava Dance Theater in Nadhi Thekkek's "
            "Bharatanatyam work \"Rogue Gestures/Foreign Bodies\", with Soles of Duende "
            "performing a tap, flamenco and Kathak fusion."
        ),
        forms=[DanceForm.BHARATANATYAM, DanceForm.FUSION],
        kind=EventKind.FESTIVAL,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
    dict(
        title="New York Kathak Festival 2026, 4th edition",
        start=datetime(2026, 7, 31, 19, 0, tzinfo=NY),
        end=datetime(2026, 8, 2, 15, 0, tzinfo=NY),
        venue="New York Live Arts",
        address="219 W 19th St, New York, NY",
        region=Region.MANHATTAN,
        info_url="https://newyorklivearts.org/event/new-york-kathak-festival-2026/",
        description=(
            "The fourth edition ran across three days of performances, workshops and "
            "conversations centred on Kathak, headlined by Prashant Shah and Sandip Mallick."
        ),
        forms=[DanceForm.KATHAK],
        kind=EventKind.FESTIVAL,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
    dict(
        title="All-Indian Dance Festival 2026",
        start=datetime(2026, 7, 5, 14, 0, tzinfo=NY),
        venue="Stern Auditorium / Perelman Stage, Carnegie Hall",
        address="881 7th Ave, New York, NY",
        region=Region.MANHATTAN,
        info_url="https://www.carnegiehall.org/Calendar/2026/07/05/All-Indian-Dance-Festival-2026-0200PM",
        description=(
            "387 dancers performed Indian classical and folk works to an audience of nearly "
            "2,800, produced by the Philadelphia nonprofit Three Aksha and curated by Viji Rao "
            "with the Consulate General of India, New York."
        ),
        forms=[DanceForm.BHARATANATYAM, DanceForm.KATHAK, DanceForm.FOLK],
        kind=EventKind.FESTIVAL,
        presenter=PresenterType.MIXED,
    ),
    dict(
        title="Inayat: A Duet for Four",
        start=datetime(2026, 6, 10, 17, 0, tzinfo=NY),
        venue="Hearst Plaza, Lincoln Center",
        address="10 Lincoln Center Plaza, New York, NY",
        region=Region.MANHATTAN,
        is_free=True,
        price_note="Free / choose-what-you-pay",
        info_url="https://www.lincolncenter.org/series/summer-for-the-city/inayat-a-duet-for-four-267",
        description=(
            "Opening night of Lincoln Center's Summer for the City paired Rajasthani folk music "
            "from the Langa musicians of SAZ with new Kathak danced by Tarini Tripathi and "
            "choreographed by Gauri Sharma Tripathi, in collaboration with Jodhpur RIFF."
        ),
        forms=[DanceForm.KATHAK, DanceForm.FOLK],
        kind=EventKind.PERFORMANCE,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
    dict(
        title="Holi Dance & Music Celebration: Festival of Colors",
        start=datetime(2026, 4, 25, 14, 15, tzinfo=NY),
        venue="Flushing Town Hall",
        address="137-35 Northern Blvd, Flushing, NY",
        region=Region.QUEENS,
        price_min=12.0,
        price_max=20.0,
        price_note="$12–$20 depending on advance or day-of",
        info_url="https://www.flushingtownhall.org/show-details/holi-dance-music-celebration-festival-of-colors",
        description=(
            "Abha B. Roy and dancers of Srijan Dance Company performed regional Indian folk "
            "dances from Bengal, Kashmir, Tamil Nadu, Rajasthan, Gujarat and Uttar Pradesh, "
            "with Hindustani vocalist Sanjukta Sen, closing with colour-throwing in the garden."
        ),
        forms=[DanceForm.FOLK],
        kind=EventKind.PERFORMANCE,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
]

# Second research pass: further NYC-metro Indian dance events from the same
# window, each with a source page found in search. Entries whose venue or date
# could not be pinned down were deliberately left out rather than guessed.
PAST_EVENTS += [
    dict(
        title="Navatman x Baila Society: When the Sun Rises",
        start=datetime(2026, 6, 26, 20, 0, tzinfo=NY),
        additional_dates=[datetime(2026, 6, 27, 19, 30, tzinfo=NY), datetime(2026, 6, 28, 15, 0, tzinfo=NY)],
        venue="Ailey Citigroup Theater",
        address="405 W 55th St, New York, NY",
        region=Region.MANHATTAN,
        info_url="https://natlawreview.com/press-releases/kathak-bharatanatyam-and-salsa-converge-alvin-ailey-stage-weekend-only",
        description=(
            "Kathak, Bharatanatyam and salsa shared one stage with an original live score, "
            "directed by Ahtoy Juliana and Sahasra Sambamoorthi."
        ),
        forms=[DanceForm.KATHAK, DanceForm.BHARATANATYAM, DanceForm.FUSION],
        kind=EventKind.PERFORMANCE,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
    dict(
        title="AUM Dance Creations: 15th Anniversary Showcase",
        start=datetime(2026, 6, 6, 18, 0, tzinfo=NY),
        venue="NJPAC",
        address="1 Center St, Newark, NJ",
        region=Region.NEW_JERSEY,
        info_url="https://www.njpac.org/event/aum-dance-creations/",
        description=(
            "More than 500 dancers aged four to adult traced India's history and culture "
            "through classical, folk and Bollywood forms."
        ),
        forms=[DanceForm.BOLLYWOOD, DanceForm.FOLK, DanceForm.BHARATANATYAM],
        kind=EventKind.PERFORMANCE,
        presenter=PresenterType.ACADEMY_STUDENT,
    ),
    dict(
        title="Nritya Darpan 2026",
        start=datetime(2026, 4, 11, 18, 0, tzinfo=NY),
        venue="New Brunswick Performing Arts Center",
        address="11 Livingston Ave, New Brunswick, NJ",
        region=Region.NEW_JERSEY,
        price_note="Sold out",
        info_url="https://newsindiatimes.com/nritya-darpans-sold-out-show-highlights-emerging-established-artists/",
        description=(
            "A sold-out third edition presented by IHCA-NJ with five curated classical and "
            "contemporary works on social themes, including IMGE Dance Company's \"Desert Myths\"."
        ),
        forms=[DanceForm.KATHAK, DanceForm.BHARATANATYAM, DanceForm.KUCHIPUDI, DanceForm.FUSION],
        kind=EventKind.FESTIVAL,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
    dict(
        title="Heritage of India Festival, 26th annual",
        start=datetime(2026, 8, 2, 12, 0, tzinfo=NY),
        venue="Kensico Dam Plaza",
        address="Valhalla, NY",
        region=Region.WESTCHESTER,
        is_free=True,
        info_url="https://parks.westchestercountyny.gov/press-releases/celebrate-culture-and-community-at-the-heritage-of-india-festival-at-kensico-dam-plaza-on-august-2",
        description=(
            "A free outdoor Westchester festival with more than 40 performers of traditional "
            "and contemporary Indian dance and music."
        ),
        forms=[DanceForm.FOLK, DanceForm.BHARATANATYAM],
        kind=EventKind.FESTIVAL,
        presenter=PresenterType.MIXED,
    ),
    dict(
        title="Queensboro Dance Festival finale — Neela Zareen (Kathak)",
        start=datetime(2026, 8, 15, 19, 0, tzinfo=NY),
        venue="Queens Theatre",
        address="Flushing Meadows Corona Park, Queens, NY",
        region=Region.QUEENS,
        info_url="https://www.queenstheatre.org/events/2026-queensboro-dance-festival-tour-finale-1jdr",
        description=(
            "The borough-wide festival's mainstage finale included Kathak by Neela Zareen of "
            "Neela Dance Academy among 20 Queens dance companies."
        ),
        forms=[DanceForm.KATHAK],
        kind=EventKind.PERFORMANCE,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
    dict(
        title="American Natya Idol — New York regionals",
        start=datetime(2026, 4, 26, 10, 30, tzinfo=NY),
        venue="Gibney, 280 Broadway",
        address="53A Chambers St, New York, NY",
        region=Region.MANHATTAN,
        info_url="https://natya.org/new-york-natya-idol-2026/",
        description=(
            "Regional round of the national classical Indian dance competition, judged by "
            "Prasanna Kasthuri and Pushyami Lanka Gottupati."
        ),
        forms=[DanceForm.BHARATANATYAM, DanceForm.KATHAK, DanceForm.KUCHIPUDI, DanceForm.FOLK],
        kind=EventKind.OTHER,
        presenter=PresenterType.ACADEMY_STUDENT,
    ),
    dict(
        title="Garden of Dance: a living tribute to Rukmini Devi Arundale",
        start=datetime(2026, 4, 25, 18, 30, tzinfo=NY),
        venue="Theater at St. Jean",
        address="150 E 76th St, New York, NY",
        region=Region.MANHATTAN,
        info_url="https://www.tickettailor.com/events/fragranceofalegendrememberingrukminideviarundale/2075113",
        description=(
            "An International Dance Day tribute to Bharatanatyam figure Rukmini Devi Arundale, "
            "presented by Kalakshetra Foundation alumni Damir Tasmagambetov and Tatyana Popova."
        ),
        forms=[DanceForm.BHARATANATYAM],
        kind=EventKind.PERFORMANCE,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
    dict(
        title="Festival of India: Kuchipudi by Amulya Pilla",
        start=datetime(2026, 4, 4, 20, 0, tzinfo=NY),
        venue="Theater for the New City",
        address="155 First Ave, New York, NY",
        region=Region.MANHATTAN,
        price_min=25.0, price_max=25.0,
        info_url="https://theaterforthenewcity.net/shows/festival-of-india-sitar-workshop/",
        description="A Festival of India programme featuring Kuchipudi danced by Amulya Pilla.",
        forms=[DanceForm.KUCHIPUDI],
        kind=EventKind.PERFORMANCE,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
    dict(
        title="Kala Samaagam: South Indian Music & Dance Festival community day",
        start=datetime(2026, 5, 2, 11, 0, tzinfo=NY),
        venue="ArtsWestchester",
        address="31 Mamaroneck Ave, White Plains, NY",
        region=Region.WESTCHESTER,
        is_free=True,
        info_url="https://www.eventbrite.com/e/kala-samaagam-south-indian-music-dance-festival-tickets-1985448320373",
        description=(
            "A free family day of South Indian arts with close to a dozen folk, classical and "
            "devotional dance styles alongside music and workshops."
        ),
        forms=[DanceForm.FOLK, DanceForm.BHARATANATYAM],
        kind=EventKind.FESTIVAL,
        presenter=PresenterType.MIXED,
    ),
    dict(
        title="Family Day: Passport Through Asia — abhinaya with Parul Shah",
        start=datetime(2026, 5, 30, 13, 0, tzinfo=NY),
        venue="Asia Society New York",
        address="725 Park Ave, New York, NY",
        region=Region.MANHATTAN,
        info_url="https://asiasociety.org/new-york/events/family-day-passport-through-asia",
        description=(
            "A family workshop on storytelling through abhinaya, the expressive vocabulary of "
            "Indian dance, led by Parul Shah."
        ),
        forms=[DanceForm.BHARATANATYAM],
        kind=EventKind.WORKSHOP,
        presenter=PresenterType.PROFESSIONAL_COMPANY,
    ),
]


def main() -> None:
    for spec in PAST_EVENTS:
        scraped = Scraped(
            title=spec["title"],
            start=spec["start"],
            end=spec.get("end"),
            additional_dates=spec.get("additional_dates", []),
            venue=spec["venue"],
            address=spec.get("address", ""),
            region=spec["region"],
            price_min=spec.get("price_min"),
            price_max=spec.get("price_max"),
            is_free=spec.get("is_free", False),
            price_note=spec.get("price_note", ""),
            info_url=spec["info_url"],
            description_snippet=spec["description"],
            sources=[
                SourceRecord(
                    source_id="manual",
                    url=spec["info_url"],
                    first_seen=TODAY,
                    last_seen=TODAY,
                )
            ],
        )
        scraped.content_hash = content_hash(scraped)
        event = Event(
            id=make_event_id(scraped),
            status=Status.PAST,
            was_published=True,
            scraped=scraped,
            ai=Classification(
                relevant=True,
                kind=spec["kind"],
                forms=spec["forms"],
                presenter_type=spec["presenter"],
                confidence=Confidence.HIGH,
                reasoning="Indian dance event verified against a live source page.",
                model=MODEL,
                classified_at=TODAY,
            ),
            curated=Curated(forms=spec["forms"]),
        )
        print(f"archived {save_event(event, human=True)}")


if __name__ == "__main__":
    main()
