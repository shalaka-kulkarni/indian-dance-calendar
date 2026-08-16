"""One-time seeding of hand-verified upcoming events
(entered 16 Aug 2026). Info URLs are
canonical org pages. Every seed carries needs_recheck=True so the first live
sweep confirms dates/times/prices against the real listings before anything
is treated as settled — and the publish checker still gates them like any
scraped event.

Run: uv run python scripts/seed.py
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pipeline.models import (
    Curated,
    DanceForm,
    Event,
    Region,
    Scraped,
    SourceRecord,
    Status,
)
from pipeline.store import content_hash, make_event_id, save_event

NY = ZoneInfo("America/New_York")
TODAY = date(2026, 8, 16)


def record(url: str) -> list[SourceRecord]:
    return [SourceRecord(source_id="manual", url=url, first_seen=TODAY, last_seen=TODAY)]


SEEDS = [
    (
        Scraped(
            title="Erasing Borders Festival of Indian Dance, 18th edition",
            start=datetime(2026, 9, 19, 18, 0, tzinfo=NY),
            additional_dates=[datetime(2026, 9, 20, 18, 0, tzinfo=NY)],
            venue="Kaye Playhouse at Hunter College",
            address="695 Park Ave, New York, NY",
            region=Region.MANHATTAN,
            price_min=20.0,
            price_max=20.0,
            price_note="from $20",
            info_url="https://iaac.us/",
            description_snippet=(
                "IAAC's annual festival; six classical forms. Radhe Jaggi & Team "
                "(Bharatanatyam + Kalaripayattu), Sreelakshmy Kallungal Govardhanan "
                "(Kuchipudi), Shila Mehta trio (Kathak), Radha Varadan (Kathak), "
                "Neena Prasad (Mohiniyattam), Arushi Mudgal (Odissi), Preeti "
                "Vasudevan (contemporary), Aparna Sindhoor."
            ),
            sources=record("https://iaac.us/"),
        ),
        Curated(
            forms=[
                DanceForm.BHARATANATYAM,
                DanceForm.KUCHIPUDI,
                DanceForm.KATHAK,
                DanceForm.MOHINIYATTAM,
                DanceForm.ODISSI,
                DanceForm.CONTEMPORARY_INDIAN,
            ]
        ),
    ),
    (
        Scraped(
            title="5th Annual Dr. Sunil Kothari Lecture: Rama Vaidyanathan",
            start=datetime(2026, 9, 24, 18, 0, tzinfo=NY),
            venue="Bruno Walter Auditorium, NYPL for the Performing Arts",
            address="111 Amsterdam Ave, New York, NY",
            region=Region.MANHATTAN,
            info_url="https://www.nypl.org/locations/lpa",
            description_snippet=(
                "Annual dance-scholarship lecture honoring critic Dr. Sunil Kothari, "
                "delivered by Bharatanatyam artist Rama Vaidyanathan."
            ),
            sources=record("https://www.nypl.org/locations/lpa"),
        ),
        Curated(forms=[DanceForm.BHARATANATYAM]),
    ),
    (
        Scraped(
            title="Nrityagram Dance Ensemble: KHANKHANA",
            start=datetime(2026, 10, 13, 19, 30, tzinfo=NY),
            end=datetime(2026, 10, 18, 19, 30, tzinfo=NY),
            venue="The Joyce Theater",
            address="175 8th Ave, New York, NY",
            region=Region.MANHATTAN,
            price_min=17.0,
            price_max=72.0,
            info_url="https://www.joyce.org/",
            description_snippet=(
                "Odissi with live music from the one fully professional tourable "
                "Indian classical ensemble. Six-day run; Curtain Chat Oct 14. "
                "Curtain times to be confirmed against the Joyce listing."
            ),
            sources=record("https://www.joyce.org/"),
        ),
        Curated(forms=[DanceForm.ODISSI]),
    ),
    (
        Scraped(
            title="Carved in Time — Mesma Belsare & Sonali Skandan",
            start=datetime(2026, 11, 14, 19, 0, tzinfo=NY),
            venue="Gibney Agnes Varis Performing Arts Center",
            address="53A Chambers St, New York, NY",
            region=Region.MANHATTAN,
            info_url="https://gibneydance.org/",
            description_snippet="Evening-length work by Mesma Belsare and Sonali Skandan.",
            sources=record("https://gibneydance.org/"),
        ),
        Curated(forms=[DanceForm.BHARATANATYAM]),
    ),
]


def main() -> None:
    for scraped, curated in SEEDS:
        scraped.content_hash = content_hash(scraped)
        event = Event(
            id=make_event_id(scraped),
            status=Status.NEEDS_ATTENTION,  # publish checker promotes on first live run
            needs_recheck=True,
            scraped=scraped,
            curated=curated,
        )
        path = save_event(event, human=True)
        print(f"seeded {path}")


if __name__ == "__main__":
    main()
