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
