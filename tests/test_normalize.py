from datetime import date

from pipeline.models import Region
from pipeline.normalize import infer_region, normalize, parse_price, parse_when
from pipeline.scrapers.base import RawEvent


def test_parse_when_iso_and_verbatim():
    assert parse_when("2026-09-18T19:30:00-04:00").hour == 19
    parsed = parse_when("September 30, 2026")
    assert (parsed.year, parsed.month, parsed.day) == (2026, 9, 30)
    assert str(parsed.tzinfo) is not None


def test_parse_when_day_range_takes_first_day():
    parsed = parse_when("Sep 19-20, 2026")
    assert (parsed.month, parsed.day) == (9, 19)


def test_parse_price_variants():
    assert parse_price("$17–$72") == (17.0, 72.0, False, "")
    assert parse_price("Free") == (0.0, 0.0, True, "")
    low, high, free, note = parse_price("from $20")
    assert (low, high, free) == (20.0, 20.0, False)
    assert note == "from $20"
    low, high, free, note = parse_price("Sold at door")
    assert low is None and note == "Sold at door"


def test_infer_region():
    assert infer_region("The Joyce Theater", "175 8th Ave, New York, NY") == Region.MANHATTAN
    assert infer_region("NJPAC", "1 Center St, Newark") == Region.NEW_JERSEY
    assert infer_region("Flushing Town Hall", "") == Region.QUEENS
    assert infer_region("Mystery Hall", "") == Region.UNKNOWN


def test_normalize_floor_requirements():
    ok = RawEvent(
        source_id="joyce",
        source_url="https://x.org/cal",
        title="Show",
        start_raw="Oct 1, 2026",
        info_url="https://x.org/show",
    )
    assert normalize(ok, today=date(2026, 8, 16)) is not None
    missing_date = RawEvent(source_id="joyce", source_url="https://x.org/cal", title="Show", info_url="https://x.org/show")
    assert normalize(missing_date, today=date(2026, 8, 16)) is None
    missing_title = RawEvent(source_id="joyce", source_url="https://x.org/cal", start_raw="Oct 1, 2026", info_url="https://x.org/show")
    assert normalize(missing_title, today=date(2026, 8, 16)) is None
