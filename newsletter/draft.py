"""Monthly email: everything added to the calendar since the last issue, plus
what is coming up.

Assembled only from published (validated) events — no AI prose, every line
traceable to a checked event file with a live link. Writes markdown to out/ and,
when BUTTONDOWN_API_KEY is set, creates the email in Buttondown.

  uv run python -m newsletter.draft            # write the draft locally
  uv run python -m newsletter.draft --send     # also push it to Buttondown
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.models import Event, Status
from pipeline.store import load_all_events

NY_TZ = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
STATE_PATH = ROOT / "data" / "newsletter_state.json"
SITE_URL = os.environ.get("SITE_URL", "https://shalaka-kulkarni.github.io/indian-dance-calendar/")


def first_seen(event: Event) -> date | None:
    dates = [r.first_seen for r in event.scraped.sources if r.first_seen]
    return min(dates) if dates else None


def fmt_when(event: Event) -> str:
    s = event.scraped
    first = s.start.strftime("%a %-d %b")
    time = s.start.strftime(" · %-I:%M%p").lower() if (s.start.hour, s.start.minute) != (0, 0) else ""
    if s.end and s.end.date() != s.start.date():
        return f"{first} – {s.end.strftime('%a %-d %b')}"
    if s.additional_dates:
        return first + " + " + ", ".join(d.strftime("%-d %b") for d in s.additional_dates)
    return f"{first}{time}"


def fmt_price(event: Event) -> str:
    s = event.scraped
    if s.is_free:
        return "Free"
    if s.price_min is not None:
        return f"${s.price_min:g}" if s.price_min == s.price_max else f"${s.price_min:g}–${s.price_max:g}"
    return s.price_note or "see listing"


def entry(event: Event) -> str:
    s = event.scraped
    forms = ", ".join(f.value.replace("_", " ").title() for f in event.effective_forms)
    line = f"**{fmt_when(event)} — {s.title}**"
    if forms:
        line += f"  \n{forms}"
    line += f"  \n{s.venue} · {fmt_price(event)}"
    line += f"  \n[Info]({s.info_url})"
    if s.ticket_url and s.ticket_url != s.info_url:
        line += f" · [Book tickets]({s.ticket_url})"
    if event.curated.editor_note:
        line += f"  \n*{event.curated.editor_note}*"
    return line


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def build_issue(now: datetime | None = None) -> tuple[str, str, int]:
    """Returns (subject, markdown body, number of events featured)."""
    now = now or datetime.now(NY_TZ)
    state = load_state()
    last_sent = date.fromisoformat(state["last_sent"]) if state.get("last_sent") else None
    cutoff = last_sent or (now.date() - timedelta(days=31))

    published = [e for e in load_all_events() if e.status == Status.PUBLISHED]
    upcoming = sorted((e for e in published if e.scraped.start >= now), key=lambda e: e.scraped.start)

    added = [e for e in upcoming if (first_seen(e) or date.min) >= cutoff]
    soon = [e for e in upcoming if e.scraped.start <= now + timedelta(days=45) and e not in added]
    free = [e for e in upcoming if e.scraped.is_free and e not in added and e not in soon]

    subject = f"Indian dance in New York — {now.strftime('%B %Y')}"
    parts = [f"# {subject}", ""]
    if added:
        parts += [f"## New since the last email ({len(added)})", ""]
        parts += [entry(e) + "\n" for e in added]
    if soon:
        parts += ["## Coming up", ""]
        parts += [entry(e) + "\n" for e in soon]
    if free:
        parts += ["## Free", ""]
        parts += [entry(e) + "\n" for e in free]
    if not (added or soon or free):
        parts += ["Nothing new on the calendar this month.", ""]
    parts += [
        "---",
        f"[See the full calendar]({SITE_URL}) · every listing links to the venue's own page,",
        "which is always the authority on dates, prices and tickets.",
    ]
    return subject, "\n".join(parts), len(added) + len(soon) + len(free)


def push_to_buttondown(subject: str, body: str, send: bool) -> None:
    key = os.environ.get("BUTTONDOWN_API_KEY")
    if not key:
        print("BUTTONDOWN_API_KEY not set — draft written locally only")
        return
    import httpx

    resp = httpx.post(
        "https://api.buttondown.com/v1/emails",
        headers={"Authorization": f"Token {key}"},
        json={
            "subject": subject,
            "body": body,
            "status": "about_to_send" if send else "draft",
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        print(f"Buttondown rejected the email ({resp.status_code}): {resp.text[:300]}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Buttondown: created email as {'send' if send else 'draft'}")
    if send:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps({"last_sent": date.today().isoformat()}, indent=1) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="newsletter.draft")
    parser.add_argument("--send", action="store_true", help="send via Buttondown instead of drafting")
    args = parser.parse_args(argv)

    now = datetime.now(NY_TZ)
    subject, body, count = build_issue(now)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"newsletter-{now.date().isoformat()}.md"
    path.write_text(body)
    print(f"{count} events · draft at {path}")
    if count == 0 and args.send:
        print("nothing to send this month; skipping")
        return 0
    push_to_buttondown(subject, body, send=args.send)
    return 0


if __name__ == "__main__":
    sys.exit(main())
