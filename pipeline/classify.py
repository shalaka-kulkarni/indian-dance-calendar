"""Claude classification: is this an Indian dance event, what form, professional
or student. Advisory only — facts never originate here. Skips gracefully when
ANTHROPIC_API_KEY is absent (events wait in needs_attention until a keyed run).

Every listing from mainstream venues gets classified — NO keyword pre-filter.
"Ragamala Dance Company: Fires of Varanasi" contains no form keyword; a keyword
filter would recreate exactly the miss this project exists to fix.
"""

from __future__ import annotations

import os
from datetime import date

from pydantic import BaseModel, ConfigDict

from pipeline.models import (
    Classification,
    Confidence,
    DanceForm,
    EventKind,
    PresenterType,
    Scraped,
)
from pipeline.scrapers.base import log

MODEL = os.environ.get("SKYD_CLASSIFY_MODEL", "claude-opus-5")

SYSTEM_PROMPT = """You classify NYC-metro event listings for an Indian dance calendar.

An event is RELEVANT only if Indian dance is performed, taught, or discussed as a
substantial part of it: classical forms (Kathak, Bharatanatyam, Odissi, Kuchipudi,
Mohiniyattam, Manipuri, Sattriya, Kathakali), Indian folk forms (garba, bhangra,
lavani, Rajasthani folk, etc.), Bollywood/filmi dance, Indian-rooted fusion or
contemporary work by Indian-form-trained artists, dance-focused lectures or
lecture-demonstrations, and dance workshops. Pure music concerts (Hindustani or
Carnatic vocal/instrumental with no dance component stated) are NOT relevant.
Non-Indian dance is NOT relevant.

presenter_type cues: touring/repertory companies, presented series, named
professional ensembles -> professional_company. School annual shows, student
recitals, arangetrams -> academy_student. Festivals mixing both -> mixed.
If the text doesn't say, use unknown.

HARD RULES:
- Judge ONLY from the text provided. If a fact is not stated, do not assume it.
- Never guess dates, prices, or names.
- confidence=high only when the text makes relevance (or irrelevance) unambiguous.
- When the title/description is too thin to tell (e.g. just an artist name you
  don't recognize from the text itself), use confidence=low."""


class ClassifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevant: bool
    kind: EventKind
    forms: list[DanceForm]
    presenter_type: PresenterType
    confidence: Confidence
    reasoning: str


def _payload(scraped: Scraped, source_name: str, circuit: str) -> str:
    price = (
        "Free" if scraped.is_free
        else f"${scraped.price_min}-${scraped.price_max}" if scraped.price_min is not None
        else scraped.price_note or "not stated"
    )
    return (
        f"Source: {source_name} (circuit: {circuit})\n"
        f"Title: {scraped.title}\n"
        f"Date: {scraped.start.isoformat()}\n"
        f"Venue: {scraped.venue or 'not stated'}\n"
        f"Price: {price}\n"
        f"Description: {scraped.description_snippet or 'none'}"
    )


def classify_event(
    scraped: Scraped,
    source_name: str,
    circuit: str,
    assume_relevant: bool = False,
    client=None,
) -> Classification | None:
    """Returns None when no API key is configured (caller leaves event pending)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    prompt = _payload(scraped, source_name, circuit)
    if assume_relevant:
        prompt += (
            "\n\nNote: this source lists Indian arts events specifically, so treat"
            " relevance as likely — but still verify the text describes dance, and"
            " focus on tagging forms and presenter_type."
        )
    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_format=ClassifyResponse,
        )
        parsed: ClassifyResponse = response.parsed_output
    except Exception as exc:  # noqa: BLE001 — one bad call must not sink the sweep
        log.warning("classification failed for %r: %s", scraped.title[:60], exc)
        return None
    return Classification(
        relevant=parsed.relevant,
        kind=parsed.kind,
        forms=parsed.forms,
        presenter_type=parsed.presenter_type,
        confidence=parsed.confidence,
        reasoning=parsed.reasoning[:400],
        model=MODEL,
        classified_at=date.today(),
    )
