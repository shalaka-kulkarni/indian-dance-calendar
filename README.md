# Rasa Calendar — Indian performing arts in New York

A self-updating public calendar of Indian dance and music across the New York
metro: classical, semi-classical and fusion, folk, contemporary, and film and
popular repertoire — merged from ~40 venue calendars, listings, platform APIs,
and a weekly broad web search, checked automatically before anything publishes.
Full design: [SPEC.md](SPEC.md).

## Go-live checklist (one-time, ~15 minutes)

The scheduled jobs are already armed on the repository's default branch, which
is where GitHub runs cron workflows.

1. **Add repo secrets** ([Settings → Secrets and variables → Actions](../../settings/secrets/actions)):
   - `ANTHROPIC_API_KEY` — required; powers event classification ([console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys))
   - `BRAVE_API_KEY` — recommended; powers weekly broad discovery (free tier at [brave.com/search/api](https://brave.com/search/api/))
   - `TICKETMASTER_KEY` — optional; free at [developer.ticketmaster.com](https://developer.ticketmaster.com/)
   - `EVENTBRITE_TOKEN` — optional; free at [eventbrite.com/platform](https://www.eventbrite.com/platform)
   Any missing key just disables that layer gracefully — nothing breaks.
2. **First sweep:** [Actions → sweep](../../actions/workflows/sweep.yml) → Run
   workflow. It scrapes every source, classifies, verifies links/dates/prices,
   and commits published events. Check the run summary and
   `python -m pipeline.run report` output.
3. **Deploy the site (free, no domain needed).** Two options:
   - *Repo stays public:* GitHub Pages works with no new accounts — ask a
     Claude session to add the Pages deploy workflow, or use the Cloudflare
     option below.
   - *Repo private (or preferred anyway):* create a free
     [Cloudflare account](https://dash.cloudflare.com/sign-up) → Workers &
     Pages → Create → Pages → *Connect to Git* → authorize GitHub and pick
     this repo → build settings:
     - Root directory: `site`
     - Build command: `npm run build`
     - Output directory: `dist`

   The site goes live at `https://<project-name>.pages.dev` and redeploys on
   every sweep commit automatically.

## Local development

```bash
make install         # uv venv + Python deps + site npm install
make test            # pytest (fixture-based, no network needed)
make sweep           # full scrape -> classify -> validate -> save (needs network)
make build           # regenerate site/src/data/events.json + calendar.ics
make site            # build the Astro site
make draft           # write out/newsletter-YYYY-MM-DD.md
uv run skyd report   # see the needs_attention queue
```

Hand-enter an event (it still passes the publish checker):

```bash
uv run skyd add --title "..." --date "Sep 19 2026 6pm" --venue "..." \
  --url https://... --tickets https://... --price "from $20" --forms kathak
```

## How it stays trustworthy

- Nothing publishes without passing checks: live links, valid future date,
  price info, metro location, confident classification.
- Every event card links its info page and ticket page separately, plus every
  source it was found in — the source is always authoritative.
- If a re-scrape shows a published event changed (moved date, cancelled), it
  comes off the site until re-verified.
- Weekly healthcheck re-verifies all published links and opens a GitHub issue
  when anything needs eyes. Scraper breakage is loud, never silent.

The four seeded events (from the verified research record) carry
`needs_recheck: true` and publish only after the first live sweep confirms
their links — same bar as everything scraped.
