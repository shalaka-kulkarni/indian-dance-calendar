"""Load and validate the source registry (data/sources.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml

from pipeline.models import Source

SOURCES_PATH = Path(__file__).resolve().parent.parent / "data" / "sources.yaml"


def load_sources(path: Path | None = None, enabled_only: bool = True) -> list[Source]:
    with open(path or SOURCES_PATH) as f:
        raw = yaml.safe_load(f)
    sources = [Source.model_validate(item) for item in raw["sources"]]
    if enabled_only:
        sources = [s for s in sources if s.enabled]
    ids = [s.id for s in sources]
    if len(ids) != len(set(ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        raise ValueError(f"duplicate source ids: {dupes}")
    return sources
