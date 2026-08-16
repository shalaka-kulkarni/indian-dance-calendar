"""Canonical data model.

Every event file has three ownership zones:
  scraped: machine-owned — the pipeline overwrites this freely on re-scrape
  ai:      machine-suggested — Claude's classification, advisory
  curated: human-owned — the pipeline must never write here (store.py enforces this)

Publishing is automatic (no human gate): an event goes live when classification
says it's an Indian dance event with sufficient confidence AND validation passes
(live links, parseable date, metro geography). Anything ambiguous or failing a
check lands in needs_attention instead of the site — visible in reports, never
silently published.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class Circuit(str, enum.Enum):
    MAINSTREAM = "mainstream"
    DIASPORA = "diaspora"
    PLATFORM = "platform"  # Eventbrite/Ticketmaster/etc.
    DISCOVERY = "discovery"  # found by the broad search job


class Strategy(str, enum.Enum):
    JSONLD = "jsonld"
    ICS = "ics"
    HTML = "html"
    API = "api"
    SEARCH = "search"
    MANUAL = "manual"


class DanceForm(str, enum.Enum):
    KATHAK = "kathak"
    BHARATANATYAM = "bharatanatyam"
    ODISSI = "odissi"
    KUCHIPUDI = "kuchipudi"
    MOHINIYATTAM = "mohiniyattam"
    MANIPURI = "manipuri"
    SATTRIYA = "sattriya"
    KATHAKALI = "kathakali"
    FOLK = "folk"
    BOLLYWOOD = "bollywood"
    FUSION = "fusion"
    CONTEMPORARY_INDIAN = "contemporary_indian"
    OTHER = "other"


class EventKind(str, enum.Enum):
    PERFORMANCE = "performance"
    FESTIVAL = "festival"
    TALK = "talk"  # lectures/lecture-demonstrations on Indian dance
    WORKSHOP = "workshop"
    OTHER = "other"


class PresenterType(str, enum.Enum):
    PROFESSIONAL_COMPANY = "professional_company"
    ACADEMY_STUDENT = "academy_student"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class Region(str, enum.Enum):
    MANHATTAN = "manhattan"
    BROOKLYN = "brooklyn"
    QUEENS = "queens"
    BRONX = "bronx"
    STATEN_ISLAND = "staten_island"
    NEW_JERSEY = "new_jersey"
    LONG_ISLAND = "long_island"
    WESTCHESTER = "westchester"
    OTHER_METRO = "other_metro"
    UNKNOWN = "unknown"


class Status(str, enum.Enum):
    PUBLISHED = "published"  # live on the site
    NEEDS_ATTENTION = "needs_attention"  # failed a check or low confidence; not on site
    REJECTED = "rejected"  # classified not-Indian-dance (kept for dedup memory)
    PAST = "past"  # event date has passed; kept as archive, shown in archive only


class Confidence(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Source(BaseModel):
    """One entry in data/sources.yaml."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    circuit: Circuit
    strategy: Strategy
    url: str = ""
    region: Region = Region.UNKNOWN
    # Diaspora/dance-specific sources: relevance is assumed, only form tagging needed.
    assume_relevant: bool = False
    # Mainstream venues: classify every listing — no keyword pre-filter.
    scrape_all_listings: bool = False
    enabled: bool = True
    notes: str = ""


class SourceRecord(BaseModel):
    """Where (and when) an event was seen. An event keeps every sighting."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    url: str
    first_seen: date
    last_seen: date


class Scraped(BaseModel):
    """Machine-owned facts, taken verbatim from sources. Never AI-generated."""

    model_config = ConfigDict(extra="forbid")

    title: str
    start: datetime
    end: datetime | None = None
    # Additional performance dates for multi-date runs (each a separate datetime).
    additional_dates: list[datetime] = Field(default_factory=list)
    venue: str
    address: str = ""
    region: Region = Region.UNKNOWN
    price_min: float | None = None
    price_max: float | None = None
    is_free: bool = False
    price_note: str = ""  # e.g. "from $25", "suggested donation" — verbatim when unparseable
    info_url: str = ""  # the event's information page
    ticket_url: str = ""  # where to buy tickets — kept separate from info_url
    description_snippet: str = ""  # truncated source text, never AI text
    content_hash: str = ""
    sources: list[SourceRecord] = Field(default_factory=list)


class Classification(BaseModel):
    """Claude's advisory read of the scraped text. Facts never originate here."""

    model_config = ConfigDict(extra="forbid")

    relevant: bool
    kind: EventKind = EventKind.PERFORMANCE
    forms: list[DanceForm] = Field(default_factory=list)
    presenter_type: PresenterType = PresenterType.UNKNOWN
    confidence: Confidence = Confidence.LOW
    reasoning: str = ""
    model: str = ""
    classified_at: date | None = None


class LinkCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    ok: bool
    status_code: int | None = None
    checked_at: datetime


class Validation(BaseModel):
    """Result of the automated publish checker (validate.py)."""

    model_config = ConfigDict(extra="forbid")

    passed: bool = False
    checks: dict[str, bool] = Field(default_factory=dict)
    link_checks: list[LinkCheck] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
    validated_at: datetime | None = None


class Curated(BaseModel):
    """Human-owned. store.py refuses pipeline writes to this zone."""

    model_config = ConfigDict(extra="forbid")

    forms: list[DanceForm] = Field(default_factory=list)
    presenter_type: PresenterType | None = None
    editor_note: str = ""
    overrides: dict[str, str | float | bool] = Field(default_factory=dict)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: Status
    # Latches True the first time an event goes live. The past-events archive
    # shows only events that were actually published — never ones that expired
    # while still stuck in the needs_attention queue.
    was_published: bool = False
    needs_recheck: bool = False
    scraped: Scraped
    ai: Classification | None = None
    validation: Validation | None = None
    curated: Curated = Field(default_factory=Curated)

    @property
    def effective_forms(self) -> list[DanceForm]:
        return self.curated.forms or (self.ai.forms if self.ai else [])

    @property
    def effective_presenter_type(self) -> PresenterType:
        if self.curated.presenter_type is not None:
            return self.curated.presenter_type
        return self.ai.presenter_type if self.ai else PresenterType.UNKNOWN

    def effective_scraped_value(self, field: str):
        """curated.overrides wins over scraped for display fields."""
        if field in self.curated.overrides:
            return self.curated.overrides[field]
        return getattr(self.scraped, field)
