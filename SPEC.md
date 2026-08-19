# skyd — NYC Indian Dance Calendar

One public, always-fresh calendar of every Indian dance event in the New York
metro area, merging the two listing worlds that never talk to each other: the
community/diaspora circuit and the mainstream venues (where Indian shows are
presented but never filed anywhere findable, and where rentals get zero
marketing from the hall).

**Product decisions:** dance only (music concerts out of scope) · calendar-first
(the site is the product; newsletter is a manual-send digest) · auto-publish
with automated checks instead of a human approval gate · comprehensive scrape
breadth plus a scheduled broad-discovery search, prioritized over
submission/relationship intake.

## How an event gets on the site

```
sources (registry + platform APIs + discovery search)
  → scrape/extract  (JSON-LD preferred, then ICS, then HTML parsing)
  → normalize       (NY timezone, price range, region)
  → dedup           (same date+venue+fuzzy title ⇒ ONE event, ALL source links kept)
  → classify        (Claude: relevant? which forms? professional or academy?)
  → validate        (the publish checker — see below)
  → publish         (site + ICS feed rebuild)
```

### The publish checker (pipeline/validate.py)

Because nothing is hand-approved, **every** event must pass all checks to go
live, and stays subject to weekly re-checks:

1. **links_live** — info URL and ticket URL answer HTTP < 400 (HEAD, GET retry)
2. **has_info_url** — an information page exists
3. **date_valid** — parseable date, not in the past
4. **price_known** — price range, free flag, or verbatim price text
5. **in_metro** — resolves to NYC boroughs / NJ / LI / Westchester
6. **classified** — Claude says relevant with medium+ confidence
   (dance-specific sources like narthaki are assume-relevant; only tagging is needed)

Failing any check ⇒ `needs_attention`: kept out of the site, listed in the
weekly healthcheck issue, never silently dropped. A re-scrape that changes a
live event's facts (moved date, new price) flags `needs_recheck` and forces
re-validation — a wrong date is the worst failure a trust product can have.
High-confidence "not Indian dance" ⇒ `rejected` (kept as dedup memory).
Past events ⇒ `past` (archived, never deleted — the archive is the dataset).

### Classification rules (pipeline/classify.py)

- **Every listing at mainstream venues is classified — no keyword pre-filter.**
  "Ragamala Dance Company: Fires of Varanasi" contains no form keyword; a
  keyword filter recreates exactly the miss this project exists to fix.
- Claude (`claude-opus-5`, structured output) judges ONLY from source text:
  never guesses dates, prices, or names; thin text ⇒ low confidence ⇒ held.
- Cost at expected volume (~100–200 listings/month): under $5/month.

## Source layers (data/sources.yaml — 40 registered)

1. **Known venues & presenters (~30):** all major Manhattan houses (Joyce,
   Carnegie full calendar incl. rentals, City Center, Lincoln Center, NYLA,
   Gibney, Skirball, Ailey Citigroup, Kaye Playhouse, Symphony Space, 92NY,
   Asia Society, MetLiveArts, WMI, Town Hall), BAM, PAC NYC, outer boroughs
   (Queens Theatre, Flushing Town Hall, LaGuardia PAC, Battery Dance, Ganesha
   Temple), New Jersey (NJPAC, Prudential Center, State Theatre NB, SOPAC,
   **Loew's Jersey Theatre** — reopening in Journal Square, watch for its
   calendar coming online), diaspora circuit (narthaki, IAAC, NY Kathak
   Festival, Consulate, Sulekha), cross-circuit listings (The Dance
   Enthusiast, NYC-ARTS, Time Out).
2. **Platform APIs:** Eventbrite, Ticketmaster Discovery (keyword × NYC-metro
   geo) — catches one-off shows at venues on nobody's list. AllEvents.in via HTML.
3. **Broad discovery (weekly):** Brave Search battery over dance-form × metro
   queries ("kathak new york", "bharatanatyam recital nj", …). New pages are
   run through the same extract→classify→validate funnel; hosts that keep
   yielding events are proposed as new registry sources via GitHub issue —
   **the registry grows itself**.

Scrape strategies are best-guesses until the first live run (this repo was
built in a network-restricted environment); the healthcheck makes wrong
guesses loud, and `strategy:` per source is a one-line fix.

## Data model (data/events/YYYY/*.yaml — one file per event)

Three ownership zones, enforced by `pipeline/store.py`:
- `scraped:` machine-owned facts, overwritten freely on re-scrape. Includes
  separate `info_url` and `ticket_url`, price min/max/free/note, all source
  sightings with first/last-seen dates.
- `ai:` Claude's advisory classification.
- `curated:` human-owned (forms override, editor note); the pipeline is
  structurally unable to write here (`CuratedWriteError`).

Data lives in git: free audit history, human-editable from the GitHub UI,
diffable re-scrapes. `site/src/data/events.json` and
is a build output, committed so the site deploy
needs only Node.

## Scheduled jobs (.github/workflows/)

| Workflow | Cadence | Does |
|---|---|---|
| `sweep.yml` | Mon/Wed/Fri ~6am ET | scrape all sources → classify → validate → rebuild → commit |
| `discovery.yml` | Sun | broad search battery → same funnel → propose new sources |
| `healthcheck.yml` | Sat | re-verify every published event's links; issue for queue + broken scrapers |
| `ci.yml` | every push | lint, tests, both builds |

Scheduled workflows run on the **default branch** — merge to main to activate.
Site deploys via Cloudflare Pages git integration watching `site/`.

## Past events archive

An event that has been published and whose last date passes flips to `past` on
the next sweep (`expire_past_events`). The site keeps six months of those in a
separate archive view: same info link, **ticket link deliberately stripped**
(nothing on sale), so people can see what they missed. Only events that were
actually published ever reach the archive — the `was_published` latch keeps
events that expired while stuck in the queue out of it. Archive entries are
re-checked for a live info link on every validate run; one that goes dead is
dropped from the site rather than shown broken.

## The site (site/, Astro, static)

Single calendar page grouped by month, plus a past-events archive. Filter
chips cover the **canonical vocabulary** — every dance form, every region
(boroughs + NJ/Long Island/Westchester), presenter type, and free — with
options that match no current event rendered **disabled/greyed out** rather
than hidden, so the shape of what's covered is always visible. `build.py`
emits those counts in `filters`. Each card: full dates/times, venue + region,
price range, form chips, and exactly two links — **Info** and **Book tickets**
(archive cards show Info only).
(Google/Apple Calendar). Honest empty/freshness states — visible staleness is
the trust killer, so the footer shows the last sweep date.

## Newsletter (newsletter/draft.py — manual send for now)

`make draft` emits `out/newsletter-YYYY-MM-DD.md`: This week / Plan ahead /
Free & low-cost, assembled only from published events, with an empty editor's
intro slot. Paste into Buttondown (free ≤100 subscribers) or Gmail and send.
When subscriber flow matters, wire Buttondown's API into a workflow — the
generator is already deterministic and provider-agnostic.

## Operator runbook (~15 min/week)

- **Glance at the healthcheck issue** (Saturdays): fix or `skyd hide` anything
  stuck in needs_attention; broken scrapers are a `strategy:` edit or a parser fix.
- **Spot fixes:** `skyd add` (hand-enter an event), `skyd tag`, `skyd note`,
  `skyd hide`. All curated-zone writes; the pipeline never overwrites them.
- **Add a source:** one stanza in `data/sources.yaml`; next sweep picks it up.
- **Discovery proposals:** skim the issue, promote productive hosts to the registry.

## Roadmap

- Wire Buttondown signup + API draft push once the site has traffic.
- Per-source bespoke parsers as the first live audit reveals which need them.
- UTM parameters on outbound links → measure awareness vs convenience.
- Submission intake (form → `skyd add`) — deliberately deferred.

## Costs

Cloudflare Pages free · GitHub Actions free tier · Claude API ~$2–5/mo ·
Brave Search free tier (2k queries/mo) · Ticketmaster/Eventbrite APIs free.
Total: **~$5/month**, no domain required (pages.dev subdomain).
