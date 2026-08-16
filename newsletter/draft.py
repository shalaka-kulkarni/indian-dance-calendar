"""Weekly newsletter draft — deterministic markdown assembled ONLY from
published (validated) events. No AI prose: every line traces to a checked
event file. The draft is written to out/newsletter-YYYY-MM-DD.md for manual
sending (paste into Buttondown/Gmail); the intro slot is intentionally empty
for the editor's own voice.

Run: uv run python -m newsletter.draft
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.models import Event, Status
from pipeline.store import load_all_events

NY_TZ = ZoneInfo("America/New_York")
OUT_DIR = Path(__file__).resolve().parent.parent / "out"


def fmt_when(event: Event) -> str:
    s = event.scraped
    first = s.start.strftime("%a %b %-d")
    time = s.start.strftime(" · %-I:%M%p").lower() if (s.start.hour, s.start.minute) != (0, 0) else ""
    if s.end and s.end.date() != s.start.date():
        return f"{first}–{s.end.strftime('%a %b %-d')}"
    extra = ""
    if s.additional_dates:
        extra = " + " + ", ".join(d.strftime("%b %-d") for d in s.additional_dates)
    return f"{first}{time}{extra}"


def fmt_price(event: Event) -> str:
    s = event.scraped
    if s.is_free:
        return "Free"
    if s.price_min is not None:
        if s.price_min == s.price_max:
            return f"${s.price_min:g}"
        return f"${s.price_min:g}–${s.price_max:g}"
    return s.price_note or "price at listing"


def entry(event: Event) -> str:
    s = event.scraped
    forms = ", ".join(f.value.replace("_", " ").title() for f in event.effective_forms)
    line = f"**{fmt_when(event)} — {s.title}**"
    if forms:
        line += f" — {forms}"
    line += f"\n{s.venue} · {fmt_price(event)} · [Info]({s.info_url})"
    if s.ticket_url and s.ticket_url != s.info_url:
        line += f" · [Tickets]({s.ticket_url})"
    if event.curated.editor_note:
        line += f"\n*{event.curated.editor_note}*"
    return line


def build_draft(now: datetime | None = None) -> str:
    now = now or datetime.now(NY_TZ)
    events = sorted(
        (e for e in load_all_events() if e.status == Status.PUBLISHED),
        key=lambda e: e.scraped.start,
    )
    week_end = now + timedelta(days=8)
    ahead_end = now + timedelta(days=45)
    this_week = [e for e in events if e.scraped.start <= week_end]
    plan_ahead = [e for e in events if week_end < e.scraped.start <= ahead_end]
    free = [e for e in events if e.scraped.is_free and e.scraped.start <= ahead_end]

    parts = [
        f"# NYC Indian Dance — week of {now.strftime('%B %-d, %Y')}",
        "",
        "_[Editor's intro — write 2-3 sentences here]_",
        "",
    ]
    if this_week:
        parts += ["## This week", ""]
        parts += [entry(e) + "\n" for e in this_week]
    if plan_ahead:
        parts += ["## Plan ahead", ""]
        parts += [entry(e) + "\n" for e in plan_ahead]
    if free:
        parts += ["## Free & low-cost", ""]
        parts += [entry(e) + "\n" for e in free]
    if not (this_week or plan_ahead):
        parts += ["_No published events in the next 45 days._", ""]
    parts += [
        "---",
        "Full calendar + subscribe link: [site URL] · Every listing links to its source.",
    ]
    return "\n".join(parts)


def main() -> None:
    now = datetime.now(NY_TZ)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"newsletter-{now.date().isoformat()}.md"
    path.write_text(build_draft(now))
    print(f"draft written to {path}")


if __name__ == "__main__":
    main()
