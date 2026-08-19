"""Claude classification: is this an Indian performing-arts event, dance or music,
which tradition, professional or student. Advisory only — facts never originate
here. Skips gracefully when ANTHROPIC_API_KEY is absent (events wait in
needs_attention until a keyed run).

Every listing from mainstream venues gets classified — NO keyword pre-filter.
"Ragamala Dance Company: Fires of Varanasi" contains no form keyword; a keyword
filter would recreate exactly the miss this project exists to fix.
"""

from __future__ import annotations

import os
from datetime import date

from pydantic import BaseModel, ConfigDict

from pipeline.models import (
    ArtForm,
    Classification,
    Confidence,
    DanceForm,
    EventKind,
    MusicStyle,
    PresenterType,
    Scraped,
    Tradition,
)
from pipeline.scrapers.base import log

MODEL = os.environ.get("SKYD_CLASSIFY_MODEL", "claude-opus-5")

SYSTEM_PROMPT = """You classify NYC-metro event listings for a calendar of Indian
performing arts — dance AND music.

An event is RELEVANT only if Indian dance or Indian music is performed, taught, or
discussed as a substantial part of it.

DANCE: classical forms (Kathak, Bharatanatyam, Odissi, Kuchipudi, Mohiniyattam,
Manipuri, Sattriya, Kathakali), Indian folk forms (garba, bhangra, lavani,
Rajasthani folk), Bollywood/filmi dance, Indian-rooted fusion or contemporary work
by Indian-form-trained artists.

MUSIC: Hindustani and Carnatic classical (vocal and instrumental — sitar, sarod,
sarangi, veena, flute, violin, tabla, mridangam), dhrupad, thumri and ghazal,
qawwali, bhajan and kirtan, filmi and Indi-pop, Indian folk music, and raga-rooted
fusion or contemporary work by Indian-trained musicians.

Also relevant: festivals, lecture-demonstrations, talks and workshops centred on
either. Community programmes count when Indian dance or music is a substantial
part of them (garba nights, Diwali or Durga Puja cultural programmes) — use
kind=community for those.

NOT relevant: non-Indian dance or music; yoga, meditation and devotional services
with no performance; film screenings; class-term registration and ongoing course
enrolment (a recurring weekly class is not an event); purely culinary, literary or
political programmes.

art_form: an event tagged "both" is listed under Dance AND under Music, so it
has to genuinely offer each. Award it in exactly two cases:
- the listing explicitly names a dance performance alongside music, or
- the event is a community programme where people dance or watch dancing —
  garba and dandiya nights, Diwali and Durga Puja programmes, Onam and similar
  celebrations (use kind=community for these too).

Everything else is dance or music, whichever the text supports:
- a dance recital with accompanying musicians is dance — live accompaniment is
  normal for dance and does not make it "both";
- a concert, recital or tour, including one with a dance item somewhere on the
  bill, is music;
- a vague listing ("cultural programme", "live entertainment") with no dance
  named and no community occasion is music. Do not guess dance into it.

A reader filtering to "dance" wants events with dancing in them. A concert must
never appear there.

traditions (shared vocabulary across dance and music, pick all that apply):
- classical: the codified traditions — Bharatanatyam, Kathak, Odissi et al.;
  Hindustani and Carnatic classical, dhrupad.
- semi_classical_fusion: thumri, ghazal, qawwali, bhajan/kirtan, light-classical
  repertoire, and raga- or classical-rooted crossover with jazz, western
  classical, electronic or other traditions.
- folk: regional folk and devotional-folk repertoire — garba, bhangra, lavani,
  baul, Rajasthani, dandiya.
- contemporary: contemporary or experimental work by Indian-trained artists that
  is not presented as classical repertoire.
- popular_film: Bollywood/filmi, Indi-pop, playback-singer concerts, film-music
  tributes.

forms: only for dance events, the specific dance form(s). Leave empty for music.
music_styles: only for music events, the specific style(s). Leave empty for dance.

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
    art_form: ArtForm
    traditions: list[Tradition]
    forms: list[DanceForm]
    music_styles: list[MusicStyle]
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
            " relevance as likely — but still verify the text describes a dance or"
            " music event rather than a class term, a service or an appeal, and"
            " focus on tagging art_form, traditions and presenter_type."
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
        art_form=parsed.art_form,
        traditions=parsed.traditions,
        # Keep the specific vocabularies on the right side of the dance/music line
        # so a mis-tagged listing can't put a sitar recital under "Kathak".
        forms=[] if parsed.art_form is ArtForm.MUSIC else parsed.forms,
        music_styles=[] if parsed.art_form is ArtForm.DANCE else parsed.music_styles,
        presenter_type=parsed.presenter_type,
        confidence=parsed.confidence,
        reasoning=parsed.reasoning[:400],
        model=MODEL,
        classified_at=date.today(),
    )
