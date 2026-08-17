"""Seed researched upcoming music and community events (Aug 2026 – Aug 2027).

Every entry was corroborated by web research against a source page that was
actually seen in search results. Anything the research flagged as uncertain —
conflicting dates, a venue name that disagreed between listings, or only a
homepage to link to — was deliberately left out rather than guessed at.

Entries are written as needs_attention; the publish workflow link-checks them
on GitHub and promotes what passes.

Run: uv run python scripts/seed_upcoming.py
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pipeline.models import (
    ArtForm,
    Classification,
    Confidence,
    Curated,
    DanceForm,
    Event,
    EventKind,
    MusicStyle,
    PresenterType,
    Region,
    Scraped,
    SourceRecord,
    Status,
    Tradition,
)
from pipeline.store import content_hash, make_event_id, save_event

NY = ZoneInfo("America/New_York")
TODAY = date(2026, 8, 17)
MODEL = "claude-fable-5"

EVENTS = [
    # ---------------- music ----------------
    dict(
        title="L. Shankar — Masters Series",
        start=datetime(2026, 9, 18, 20, 0, tzinfo=NY),
        venue="Adler Hall, New York Society for Ethical Culture",
        address="2 W 64th St, New York, NY", region=Region.MANHATTAN,
        info_url="https://worldmusiccentral.org/l-shankar-to-present-decades-of-violin-innovation-in-manhattan/",
        description="World Music Institute presents violinist L. Shankar, co-founder of Shakti, in a programme spanning decades of Carnatic and East–West fusion work.",
        art_form=ArtForm.MUSIC, traditions=[Tradition.CLASSICAL, Tradition.SEMI_CLASSICAL_FUSION],
        music_styles=[MusicStyle.CARNATIC, MusicStyle.FUSION_MUSIC], kind=EventKind.PERFORMANCE,
    ),
    dict(
        title="Rakesh Chaurasia & Salar Nader",
        start=datetime(2026, 10, 2, 20, 0, tzinfo=NY),
        venue="Adler Hall, New York Society for Ethical Culture",
        address="2 W 64th St, New York, NY", region=Region.MANHATTAN,
        info_url="https://ethical.nyc/events/worldclassmusic-live-presents-rakesh-chaurasia-salar-nader/",
        ticket_url="https://tickets.worldclassmusic.live/events/wcml",
        description="Bansuri player Rakesh Chaurasia with Afghan tabla player Salar Nader.",
        art_form=ArtForm.MUSIC, traditions=[Tradition.CLASSICAL],
        music_styles=[MusicStyle.HINDUSTANI], kind=EventKind.PERFORMANCE,
    ),
    dict(
        title="Rahat Fateh Ali Khan live in concert",
        start=datetime(2026, 10, 3, 0, 0, tzinfo=NY),
        venue="Nassau Veterans Memorial Coliseum",
        address="Uniondale, NY", region=Region.LONG_ISLAND,
        info_url="https://www.ticketmaster.com/rahat-fateh-ali-khan-uniondale-new-york-10-03-2026/event/00006486D4A6C91E",
        description="Qawwali and Sufi vocalist Rahat Fateh Ali Khan in concert.",
        art_form=ArtForm.MUSIC, traditions=[Tradition.SEMI_CLASSICAL_FUSION],
        music_styles=[MusicStyle.QAWWALI], kind=EventKind.PERFORMANCE,
    ),
    dict(
        title="Ragas Live Festival 2026",
        start=datetime(2026, 10, 17, 0, 0, tzinfo=NY),
        end=datetime(2026, 10, 18, 0, 0, tzinfo=NY),
        venue="Pioneer Works", address="159 Pioneer St, Brooklyn, NY", region=Region.BROOKLYN,
        info_url="https://pioneerworks.org/programs/ragas-live-festival-2026",
        ticket_url="https://www.eventbrite.com/e/ragas-live-festival-2026-tickets-1989613275867",
        description="The 24-hour raga marathon returns to Pioneer Works with more than 50 artists across South Asian classical and contemporary collaborations. Full line-up announced in September.",
        art_form=ArtForm.MUSIC, traditions=[Tradition.CLASSICAL, Tradition.CONTEMPORARY],
        music_styles=[MusicStyle.HINDUSTANI, MusicStyle.FUSION_MUSIC], kind=EventKind.FESTIVAL,
    ),
    dict(
        title="Niladri Kumar: The Space Between the Notes",
        start=datetime(2026, 11, 5, 20, 0, tzinfo=NY),
        venue="Adler Hall, New York Society for Ethical Culture",
        address="2 W 64th St, New York, NY", region=Region.MANHATTAN,
        price_min=45.0, price_max=45.0, price_note="$45 advance",
        info_url="https://www.worldmusicinstitute.org/niladri-kumar-at-adler-hall/",
        description="Sitarist Niladri Kumar performs a programme drawn from his recorded work with the late Zakir Hussain.",
        art_form=ArtForm.MUSIC, traditions=[Tradition.CLASSICAL],
        music_styles=[MusicStyle.HINDUSTANI], kind=EventKind.PERFORMANCE,
    ),
    dict(
        title="Naad 2027: a festival of Indian music",
        start=datetime(2027, 5, 21, 19, 30, tzinfo=NY),
        end=datetime(2027, 5, 23, 15, 0, tzinfo=NY),
        venue="Carnegie Hall", address="881 7th Ave, New York, NY", region=Region.MANHATTAN,
        info_url="https://www.carnegiehall.org/Events/Highlights/Festivals-and-Artistic-Focuses/Naad-2027",
        description="Carnegie Hall's inaugural Indian music festival across three days: Rakesh Chaurasia in Zankel Hall (21 May), A.R. Rahman's Carnegie Hall debut on the Stern Auditorium stage (22 May), and SIFAR led by Kaushiki Chakraborty with Ambi Subramaniam, Soumik Datta and Ishaan Ghosh (23 May).",
        art_form=ArtForm.MUSIC, traditions=[Tradition.CLASSICAL, Tradition.POPULAR_FILM],
        music_styles=[MusicStyle.HINDUSTANI, MusicStyle.CARNATIC, MusicStyle.FILMI],
        kind=EventKind.FESTIVAL,
    ),
    # ---------------- community celebrations ----------------
    dict(
        title="KHNJ Mega Onam 2026",
        start=datetime(2026, 8, 29, 0, 0, tzinfo=NY),
        venue="Fine Arts Center, Jackson Township school complex",
        address="Jackson, NJ", region=Region.NEW_JERSEY,
        info_url="https://www.khnj.us/post/khnj-mega-onam-2026",
        description="Kerala Hindus of New Jersey's Onam celebration with traditional dances, Chenda Melam, children's performances and Sadhya.",
        art_form=ArtForm.BOTH, traditions=[Tradition.FOLK], forms=[DanceForm.FOLK],
        music_styles=[MusicStyle.FOLK_MUSIC], kind=EventKind.COMMUNITY,
        presenter=PresenterType.MIXED,
    ),
    dict(
        title="Sacha Garba Ramzat 2026 with Geeta Rabari",
        start=datetime(2026, 9, 18, 21, 0, tzinfo=NY),
        venue="Meadowlands Exposition Center", address="Secaucus, NJ", region=Region.NEW_JERSEY,
        info_url="https://www.premiertickets.co/event/sacha-garba-ramzat-2026-with-geeta-rabari-in-new-jersey/",
        description="Navratri garba night with Gujarati singer Geeta Rabari.",
        art_form=ArtForm.BOTH, traditions=[Tradition.FOLK], forms=[DanceForm.FOLK],
        music_styles=[MusicStyle.FOLK_MUSIC], kind=EventKind.COMMUNITY,
        presenter=PresenterType.MIXED,
    ),
    dict(
        title="Sacha Navratri 2026 with Kinjal Dave",
        start=datetime(2026, 9, 19, 21, 0, tzinfo=NY),
        venue="Meadowlands Exposition Center", address="Secaucus, NJ", region=Region.NEW_JERSEY,
        info_url="https://www.premiertickets.co/event/sacha-navratri-2026-with-kinjal-dave-in-new-jersey/",
        description="Navratri garba and dandiya night with Gujarati singer Kinjal Dave.",
        art_form=ArtForm.BOTH, traditions=[Tradition.FOLK], forms=[DanceForm.FOLK],
        music_styles=[MusicStyle.FOLK_MUSIC], kind=EventKind.COMMUNITY,
        presenter=PresenterType.MIXED,
    ),
    dict(
        title="Garba Around the Globe",
        start=datetime(2026, 9, 19, 17, 0, tzinfo=NY),
        venue="Unisphere, Flushing Meadows Corona Park",
        address="Queens, NY", region=Region.QUEENS,
        info_url="https://www.eventbrite.com/e/garba-around-the-globe-tickets-1992664047808",
        description="Open-air garba and dandiya at the Unisphere with live dhol, presented by Vivarta Arts.",
        art_form=ArtForm.BOTH, traditions=[Tradition.FOLK], forms=[DanceForm.FOLK],
        music_styles=[MusicStyle.FOLK_MUSIC], kind=EventKind.COMMUNITY,
        presenter=PresenterType.MIXED,
    ),
    dict(
        title="Trinayani USA Durga Puja 2026",
        start=datetime(2026, 10, 17, 0, 0, tzinfo=NY),
        end=datetime(2026, 10, 18, 0, 0, tzinfo=NY),
        venue="Trinayani USA, Plainsboro", address="Plainsboro, NJ", region=Region.NEW_JERSEY,
        info_url="https://trinayaninj.org/durgapuja2026/",
        description="Two-day Bengali Durga Puja with traditional rituals and evening concerts by Chandrabindoo and Neeraj Shridhar's Bombay Vikings.",
        art_form=ArtForm.BOTH, traditions=[Tradition.FOLK, Tradition.POPULAR_FILM],
        forms=[DanceForm.FOLK], music_styles=[MusicStyle.FOLK_MUSIC, MusicStyle.FILMI],
        kind=EventKind.COMMUNITY, presenter=PresenterType.MIXED,
    ),
    dict(
        title="Diwali on the Hudson 2026",
        start=datetime(2026, 10, 22, 19, 0, tzinfo=NY),
        venue="HK HALL", address="605 W 48th St, New York, NY", region=Region.MANHATTAN,
        info_url="https://events.sulekha.com/diwali-on-the-hudson-2026_event-in_new-york-ny_399524",
        description="Long-running Manhattan Diwali celebration with live entertainment and dancing.",
        art_form=ArtForm.BOTH, traditions=[Tradition.POPULAR_FILM, Tradition.FOLK],
        forms=[DanceForm.BOLLYWOOD], music_styles=[MusicStyle.FILMI],
        kind=EventKind.COMMUNITY, presenter=PresenterType.MIXED,
    ),
]


def main() -> None:
    for spec in EVENTS:
        scraped = Scraped(
            title=spec["title"], start=spec["start"], end=spec.get("end"),
            venue=spec["venue"], address=spec.get("address", ""), region=spec["region"],
            price_min=spec.get("price_min"), price_max=spec.get("price_max"),
            is_free=spec.get("is_free", False), price_note=spec.get("price_note", ""),
            info_url=spec["info_url"], ticket_url=spec.get("ticket_url", ""),
            description_snippet=spec["description"],
            sources=[SourceRecord(source_id="manual", url=spec["info_url"],
                                  first_seen=TODAY, last_seen=TODAY)],
        )
        scraped.content_hash = content_hash(scraped)
        event = Event(
            id=make_event_id(scraped), status=Status.NEEDS_ATTENTION, needs_recheck=True,
            scraped=scraped,
            ai=Classification(
                relevant=True, kind=spec["kind"], art_form=spec["art_form"],
                traditions=spec["traditions"], forms=spec.get("forms", []),
                music_styles=spec.get("music_styles", []),
                presenter_type=spec.get("presenter", PresenterType.PROFESSIONAL_COMPANY),
                confidence=Confidence.HIGH,
                reasoning="Researched and corroborated against a source page found in search.",
                model=MODEL, classified_at=TODAY),
            curated=Curated(forms=spec.get("forms", []), art_form=spec["art_form"],
                            traditions=spec["traditions"],
                            music_styles=spec.get("music_styles", [])),
        )
        print(f"seeded {save_event(event, human=True).name}")


if __name__ == "__main__":
    main()
