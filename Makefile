.PHONY: install sweep discover classify validate build site test lint draft

install:
	uv venv --allow-existing && uv pip install -e ".[dev]"
	cd site && npm install

# Full pipeline: scrape all registered sources, classify, validate, write events
sweep:
	uv run python -m pipeline.run sweep

# Broad discovery: search-API battery for events/venues we don't know about
discover:
	uv run python -m pipeline.run discover

classify:
	uv run python -m pipeline.run classify

# Re-verify links/dates/prices on everything published
validate:
	uv run python -m pipeline.run validate

# Emit site/src/data/events.json + site/public/calendar.ics from data/events
build:
	uv run python -m pipeline.run build

site: build
	cd site && npm run build

draft:
	uv run python -m newsletter.draft

test:
	uv run pytest

lint:
	uv run ruff check pipeline cli newsletter tests
