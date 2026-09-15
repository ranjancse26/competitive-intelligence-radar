from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

from .config import settings


class SignalType(str, Enum):
    """Types of competitive signals detected."""
    STRATEGIC_ANNOUNCEMENT = "strategic_announcement"
    NEW_JOBS = "new_jobs"
    NEW_PRODUCT = "new_product"
    SEO_MOVEMENT = "seo_movement"
    NEWS_ACTIVITY = "news_activity"
    PRESS_RELEASE = "press_release"
    PARTNERSHIP = "partnership"
    ACQUISITION = "acquisition"
    PRICING = "pricing"
    REGULATORY = "regulatory"


class Severity(str, Enum):
    """Severity levels for competitive signals."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Competitor(BaseModel):
    """A competitor to track."""
    name: str
    aliases: List[str] = Field(default_factory=list)


class RadarRequest(BaseModel):
    """Request body for running the competitive radar."""
    competitors: List[str] = Field(
        default_factory=lambda: list(settings.default_competitors)
    )
    keywords: List[str] = Field(
        default_factory=lambda: list(settings.default_keywords)
    )
    days_back: int = Field(default=settings.default_days_back, ge=1, le=30)


class Signal(BaseModel):
    """A single competitive intelligence signal."""
    competitor: str
    type: SignalType
    severity: Severity
    title: str
    description: str
    url: Optional[str] = None
    source: str
    date: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RawSearchResult(BaseModel):
    """A raw search result item aggregated from all search sources."""
    source: str
    engine: str
    title: str
    snippet: str
    url: Optional[str] = None
    date: Optional[str] = None
    thumbnail: Optional[str] = None
    position: Optional[int] = None
    rating: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CompetitorRadar(BaseModel):
    """Radar results for a single competitor."""
    competitor: str
    signals: List[Signal] = Field(default_factory=list)
    score: float = 0.0
    movement_level: str = "none"  # none, low, medium, high
    summary: str = ""
    detailed_summary: str = ""  # Comprehensive per-competitor narrative analysis
    raw_results: List[RawSearchResult] = Field(default_factory=list)  # All raw search results aggregated
    search_sources: List[str] = Field(default_factory=list)  # Which search engines/sources were queried
    signal_breakdown: Dict[str, int] = Field(default_factory=dict)  # Counts of signals by type and severity
    total_raw_results: int = 0  # Total number of raw results collected


class RadarResponse(BaseModel):
    """Full radar response with all competitors and AI summary."""
    competitors: List[CompetitorRadar]
    ai_executive_summary: str
    detailed_ai_summary: str = ""  # Expanded, multi-paragraph AI analysis
    generated_at: str
    total_signals: int
    total_raw_results: int = 0  # Aggregate count of all raw search results across competitors
    search_metadata: Dict[str, Any] = Field(default_factory=dict)  # Metadata about the search run
