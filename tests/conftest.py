from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pipeline.models import Event, Region, Scraped, SourceRecord, Status
from pipeline.store import content_hash, make_event_id

FIXTURES = Path(__file__).parent / "fixtures"
NY = ZoneInfo("America/New_York")


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture
def sample_scraped() -> Scraped:
    scraped = Scraped(
        title="Nrityagram Dance Ensemble: KHANKHANA",
        start=datetime(2026, 10, 13, 19, 30, tzinfo=NY),
        venue="The Joyce Theater",
        region=Region.MANHATTAN,
        price_min=17.0,
        price_max=72.0,
        info_url="https://www.joyce.org/nrityagram",
        ticket_url="https://tickets.joyce.org/nrityagram",
        description_snippet="Odissi with live music.",
        sources=[
            SourceRecord(
                source_id="joyce",
                url="https://www.joyce.org/nrityagram",
                first_seen=date(2026, 8, 1),
                last_seen=date(2026, 8, 1),
            )
        ],
    )
    scraped.content_hash = content_hash(scraped)
    return scraped


@pytest.fixture
def sample_event(sample_scraped) -> Event:
    return Event(
        id=make_event_id(sample_scraped),
        status=Status.NEEDS_ATTENTION,
        scraped=sample_scraped,
    )
