from pipeline import run
from pipeline.models import Classification, Confidence, Status


def test_validate_skips_rejected_events(monkeypatch, sample_event):
    rejected = sample_event.model_copy(deep=True)
    rejected.status = Status.REJECTED
    rejected.ai = Classification(relevant=False, confidence=Confidence.HIGH)
    pending = sample_event.model_copy(deep=True)
    pending.id = "other"

    checked, saved = [], []
    monkeypatch.setattr(run, "load_all_events", lambda: [rejected, pending])
    monkeypatch.setattr(run, "save_event", lambda e: saved.append(e.id))
    monkeypatch.setattr(run, "expire_past_events", lambda: 0)
    monkeypatch.setattr(run, "load_sources", lambda enabled_only=False: [])

    real_validate = run.validate_event

    def fake_validate(event, **kwargs):
        checked.append(event.id)
        return real_validate(event, check_links=False)

    monkeypatch.setattr(run, "validate_event", fake_validate)
    stats = run.cmd_validate(check_links=False)
    assert checked == ["other"]
    assert rejected.id not in saved
    assert stats["rejected"] == 1
