from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.models import (
    Classification,
    Confidence,
    DanceForm,
    EventKind,
    PresenterType,
    Status,
)
from pipeline.validate import apply_publish_policy, validate_event

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=NY)


def relevant_ai(confidence=Confidence.HIGH, relevant=True) -> Classification:
    return Classification(
        relevant=relevant,
        kind=EventKind.PERFORMANCE,
        forms=[DanceForm.ODISSI],
        presenter_type=PresenterType.PROFESSIONAL_COMPANY,
        confidence=confidence,
    )


def test_offline_run_never_publishes(sample_event):
    sample_event.ai = relevant_ai()
    validation = validate_event(sample_event, client=None, check_links=False, now=NOW)
    assert not validation.passed
    assert "links not yet verified (offline run)" in validation.problems
    assert apply_publish_policy(sample_event, validation) == Status.NEEDS_ATTENTION


def test_unclassified_event_is_held(sample_event):
    validation = validate_event(sample_event, check_links=False, now=NOW)
    assert not validation.checks["classified"]


def test_low_confidence_is_held(sample_event):
    sample_event.ai = relevant_ai(confidence=Confidence.LOW)
    validation = validate_event(sample_event, check_links=False, now=NOW)
    assert not validation.checks["classified"]


def test_confident_irrelevant_is_rejected(sample_event):
    sample_event.ai = relevant_ai(relevant=False)
    validation = validate_event(sample_event, check_links=False, now=NOW)
    assert apply_publish_policy(sample_event, validation) == Status.REJECTED


def test_past_event_fails_date_check(sample_event):
    late = datetime(2026, 12, 1, tzinfo=NY)
    sample_event.ai = relevant_ai()
    validation = validate_event(sample_event, check_links=False, now=late)
    assert not validation.checks["date_valid"]


def test_fully_valid_event_publishes(sample_event, monkeypatch):
    from pipeline import validate as validate_module
    from pipeline.models import LinkCheck

    sample_event.ai = relevant_ai()
    monkeypatch.setattr(
        validate_module,
        "check_link",
        lambda client, url: LinkCheck(url=url, ok=True, status_code=200, checked_at=NOW),
    )
    validation = validate_event(sample_event, client=object(), check_links=True, now=NOW)
    assert validation.passed, validation.problems
    assert apply_publish_policy(sample_event, validation) == Status.PUBLISHED
    assert len(validation.link_checks) == 2  # info + ticket URLs checked separately


def test_past_event_validation_is_link_only(sample_event):
    from pipeline.models import LinkCheck, Status
    from pipeline.validate import validate_past_event

    sample_event.status = Status.PAST
    sample_event.was_published = True

    class FakeClient:
        pass

    import pipeline.validate as vmod

    original = vmod.check_link
    vmod.check_link = lambda client, url: LinkCheck(url=url, ok=True, status_code=200, checked_at=NOW)
    try:
        validation = validate_past_event(sample_event, client=FakeClient(), now=NOW)
    finally:
        vmod.check_link = original
    # Past date and missing tickets must not fail an archive entry.
    assert validation.passed
    assert set(validation.checks) == {"has_info_url", "links_live"}


def test_bare_homepage_url_blocks_publication(sample_event, monkeypatch):
    """A live link is not a useful one: a homepage passes reachability but tells
    the reader nothing about the event, so it must not publish."""
    from pipeline import validate as validate_module
    from pipeline.models import LinkCheck

    sample_event.ai = relevant_ai()
    sample_event.scraped.info_url = "https://gibneydance.org/"
    sample_event.scraped.ticket_url = ""
    monkeypatch.setattr(
        validate_module,
        "check_link",
        lambda client, url: LinkCheck(url=url, ok=True, status_code=200, checked_at=NOW),
    )
    validation = validate_event(sample_event, client=object(), check_links=True, now=NOW)
    assert validation.checks["links_live"] is True  # the link works...
    assert validation.checks["specific_url"] is False  # ...but points nowhere useful
    assert not validation.passed
    assert apply_publish_policy(sample_event, validation) == Status.NEEDS_ATTENTION


def test_offline_past_validation_never_records_a_dead_link(sample_event):
    """'Not yet checked' must not be stored as 'dead', which would empty the archive."""
    from pipeline.models import Status as S
    from pipeline.validate import validate_past_event

    sample_event.status = S.PAST
    sample_event.was_published = True
    sample_event.validation = None
    validation = validate_past_event(sample_event, client=None, now=NOW)
    assert "links_live" not in validation.checks


def test_bot_blocked_link_is_not_treated_as_dead(monkeypatch):
    """Carnegie Hall and friends answer bots with 403 while serving humans fine.
    Deleting those listings is a worse failure than keeping an unverifiable link."""

    from pipeline.validate import check_link

    class FakeResponse:
        def __init__(self, code):
            self.status_code = code

    class FakeClient:
        def __init__(self, code):
            self.code = code

        def head(self, url, **kw):
            return FakeResponse(self.code)

        def get(self, url, **kw):
            return FakeResponse(self.code)

    for code in (403, 405, 429, 500):
        assert check_link(FakeClient(code), "https://example.org/e").ok, code
    for code in (404, 410):
        assert not check_link(FakeClient(code), "https://example.org/e").ok, code


def test_unreachable_link_is_unknown_not_dead(monkeypatch):
    """A timeout or reset is not a verdict. Treating one as 'dead' pulled two
    live, correct events off the calendar during a sweep. Only 404/410 remove a
    link — the same reasoning that spares 403 and 5xx."""
    import httpx

    from pipeline.validate import check_link

    class ExplodingClient:
        def __init__(self):
            self.gets = 0

        def head(self, url, **kw):
            raise httpx.ConnectError("no route")

        def get(self, url, **kw):
            self.gets += 1
            raise httpx.ConnectError("no route")

    client = ExplodingClient()
    result = check_link(client, "https://example.org/e")
    assert result.ok
    assert result.status_code is None
    # It retries with GET before concluding it cannot be reached.
    assert client.gets == 1


def test_a_head_failure_still_publishes_when_get_succeeds():
    import httpx

    from pipeline.validate import check_link

    class HeadHostileClient:
        def head(self, url, **kw):
            raise httpx.ReadTimeout("slow")

        def get(self, url, **kw):
            class R:
                status_code = 200

            return R()

    check = check_link(HeadHostileClient(), "https://example.org/e")
    assert check.ok and check.status_code == 200


def test_low_confidence_is_held_even_at_a_trusted_source(sample_event):
    """assume_relevant vouches for the subject, not for the listing being an
    event. A dance-and-music organisation's calendar also carries class terms
    and socials, and thin text on one of those must not auto-publish."""
    sample_event.ai = relevant_ai(confidence=Confidence.LOW)
    result = validate_event(sample_event, assume_relevant=True, check_links=False, now=NOW)
    assert result.checks["classified"] is False
    assert any("confidence" in p for p in result.problems)


def test_medium_confidence_still_publishes_at_a_trusted_source(sample_event):
    sample_event.ai = relevant_ai(confidence=Confidence.MEDIUM)
    result = validate_event(sample_event, assume_relevant=True, check_links=False, now=NOW)
    assert result.checks["classified"] is True
