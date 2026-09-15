import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging

from .schemas import (
    Signal,
    SignalType,
    Severity,
    CompetitorRadar,
    RadarRequest,
    RawSearchResult,
)
from .searchapi_client import SearchAPIClient
from .config import settings

logger = logging.getLogger(__name__)

# Load signal classification keywords from JSON config
_KEYWORDS_PATH = Path(__file__).resolve().parent.parent / "config" / "signal_keywords.json"


def _load_keywords() -> Dict[str, List[str]]:
    """Load signal classification keywords from the JSON config file."""
    path = Path(settings.signal_keywords_path) if settings.signal_keywords_path else _KEYWORDS_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "strategic": data.get("strategic_keywords", []),
            "product": data.get("product_keywords", []),
            "pricing": data.get("pricing_keywords", []),
            "regulatory": data.get("regulatory_keywords", []),
            "seo": data.get("seo_keywords", []),
        }
    except Exception as e:
        logger.warning(f"Failed to load signal keywords from {path}: {e}")
        return {
            "strategic": [],
            "product": [],
            "pricing": [],
            "regulatory": [],
            "seo": [],
        }


KEYWORDS = _load_keywords()
STRATEGIC_KEYWORDS = KEYWORDS["strategic"]
PRODUCT_KEYWORDS = KEYWORDS["product"]
PRICING_KEYWORDS = KEYWORDS["pricing"]
REGULATORY_KEYWORDS = KEYWORDS["regulatory"]
SEO_KEYWORDS = KEYWORDS["seo"]


def _extract_date(item: Dict[str, Any]) -> Optional[str]:
    """Extract and normalize the date string from a search result item (YYYY-MM-DD)."""
    raw = None
    for key in ["date", "published_date", "published_at", "timestamp", "date_published", "posted_at"]:
        if item.get(key):
            raw = str(item[key])
            break
    if not raw:
        return None
    dt = _parse_date_string(raw)
    if dt is not None:
        return dt.strftime("%Y-%m-%d")
    return raw


def _parse_date_string(value: Any) -> Optional[datetime]:
    """Parse a SearchAPI date string into a datetime using regex heuristics."""
    if not value:
        return None
    s = str(value).strip()

    # ISO date: 2024-01-05
    iso = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if iso:
        try:
            return datetime.strptime(iso.group(0), "%Y-%m-%d")
        except ValueError:
            pass

    # Relative: "3 days ago", "5 hours ago"
    rel = re.search(
        r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", s, re.I
    )
    if rel:
        n = int(rel.group(1))
        unit = rel.group(2).lower()
        span = {
            "second": timedelta(seconds=n),
            "minute": timedelta(minutes=n),
            "hour": timedelta(hours=n),
            "day": timedelta(days=n),
            "week": timedelta(weeks=n),
            "month": timedelta(days=n * 30),
            "year": timedelta(days=n * 365),
        }[unit]
        return datetime.now() - span

    # Month name: "Jan 5, 2024" / "January 5 2024"
    mon = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|"
        r"november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\.?\s+"
        r"(\d{1,2}),?\s+(\d{4})",
        s,
        re.I,
    )
    if mon:
        fmt = "%B %d, %Y" if len(mon.group(1)) > 3 else "%b %d, %Y"
        try:
            return datetime.strptime(mon.group(0), fmt)
        except ValueError:
            pass

    return None


def _is_recent(date_value: Optional[str], days_back: int) -> bool:
    """Return True if the date is within the look-back window.

    Items without a parseable date are kept (treated as recent) so that
    recency filtering never silently drops results it cannot evaluate.
    """
    if not date_value:
        return True
    dt = _parse_date_string(date_value)
    if dt is None:
        return True
    cutoff = datetime.now() - timedelta(days=days_back)
    return dt >= cutoff


def _extract_source(item: Dict[str, Any]) -> Optional[str]:
    """Extract the real publisher/source name from the SearchAPI response."""
    for key in ["source", "via", "publication", "publisher"]:
        if item.get(key):
            return str(item[key])
    return None


def _extract_job_details(item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the structured, high-value fields SearchAPI returns for job postings."""
    ext = item.get("detected_extensions") or {}
    return {
        "location": item.get("location"),
        "salary": ext.get("salary"),
        "posted_at": ext.get("posted_at"),
        "job_type": ext.get("schedule_type"),
        "extensions": item.get("extensions") or [],
    }


def _extract_thumbnail(item: Dict[str, Any]) -> Optional[str]:
    """Extract a thumbnail/image URL from a search result item."""
    for key in ["thumbnail", "thumbnail_url", "image", "icon"]:
        if item.get(key):
            return str(item[key])
    return None


def _extract_position(item: Dict[str, Any]) -> Optional[int]:
    """Extract the result's ranking position from the SearchAPI response."""
    pos = item.get("position")
    if pos is None:
        return None
    try:
        return int(pos)
    except (TypeError, ValueError):
        return None


def _extract_rating(item: Dict[str, Any]) -> Optional[float]:
    """Extract a numeric rating from the SearchAPI response, if present."""
    rating = item.get("rating")
    if rating is None:
        return None
    try:
        return float(rating)
    except (TypeError, ValueError):
        return None


def _extra_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    """Collect any additional structured fields returned by SearchAPI for context."""
    extra: Dict[str, Any] = {}
    for key in ["displayed_link", "via", "company_name", "related_links", "sitelinks", "extensions"]:
        val = item.get(key)
        if val:
            extra[key] = val
    return extra


def _extract_url(item: Dict[str, Any]) -> Optional[str]:
    """Extract a URL from a search result item."""
    for key in ["link", "url", "href", "news_link"]:
        if item.get(key):
            return str(item[key])
    return None


def _extract_title(item: Dict[str, Any]) -> str:
    """Extract a title from a search result item."""
    for key in ["title", "headline", "name", "job_title"]:
        if item.get(key):
            return str(item[key])
    return ""


def _extract_snippet(item: Dict[str, Any]) -> str:
    """Extract a snippet/description from a search result item."""
    for key in ["snippet", "description", "summary", "body", "text"]:
        if item.get(key):
            return str(item[key])
    return ""


def _classify_signal(
    title: str, snippet: str, source: str
) -> Tuple[SignalType, Severity]:
    """Classify a search result into a signal type and severity."""
    text = f"{title} {snippet}".lower()

    # Check for strategic announcements
    if any(kw in text for kw in STRATEGIC_KEYWORDS):
        if any(kw in text for kw in ["acquisition", "acquires", "merger", "merges"]):
            return SignalType.ACQUISITION, Severity.HIGH
        if any(kw in text for kw in ["partnership", "partners", "collaboration"]):
            return SignalType.PARTNERSHIP, Severity.HIGH
        return SignalType.STRATEGIC_ANNOUNCEMENT, Severity.HIGH

    # Check for new products
    if any(kw in text for kw in PRODUCT_KEYWORDS):
        return SignalType.NEW_PRODUCT, Severity.MEDIUM

    # Check for pricing activity
    if any(kw in text for kw in PRICING_KEYWORDS):
        return SignalType.PRICING, Severity.MEDIUM

    # Check for regulatory activity
    if any(kw in text for kw in REGULATORY_KEYWORDS):
        return SignalType.REGULATORY, Severity.MEDIUM

    # Check for SEO movement
    if any(kw in text for kw in SEO_KEYWORDS):
        return SignalType.SEO_MOVEMENT, Severity.LOW

    # Default to news activity
    if "job" in text or "hiring" in text or "career" in text:
        return SignalType.NEW_JOBS, Severity.MEDIUM

    return SignalType.NEWS_ACTIVITY, Severity.LOW


def _deduplicate(signals: List[Signal]) -> List[Signal]:
    """Remove duplicate signals based on title."""
    seen = set()
    unique = []
    for signal in signals:
        key = signal.title.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(signal)
    return unique


def _score_competitor(signals: List[Signal]) -> float:
    """Calculate a competitive movement score for a competitor."""
    score = 0.0
    for signal in signals:
        if signal.severity == Severity.HIGH:
            score += 3.0
        elif signal.severity == Severity.MEDIUM:
            score += 2.0
        else:
            score += 1.0

        # Bonus for specific signal types
        if signal.type in [SignalType.ACQUISITION, SignalType.PARTNERSHIP]:
            score += 2.0
        elif signal.type == SignalType.STRATEGIC_ANNOUNCEMENT:
            score += 1.5
        elif signal.type == SignalType.NEW_PRODUCT:
            score += 1.0
        elif signal.type == SignalType.NEW_JOBS:
            score += 0.5

    return round(score, 1)


def _movement_level(score: float) -> str:
    """Convert a score to a movement level."""
    if score >= 10:
        return "high"
    elif score >= 5:
        return "medium"
    elif score > 0:
        return "low"
    return "none"


def _build_summary(competitor: str, signals: List[Signal]) -> str:
    """Build a human-readable summary for a competitor."""
    if not signals:
        return f"No significant competitive movement detected for {competitor}."

    top_signals = signals
    parts = []
    for s in top_signals:
        parts.append(f"{s.type.value.replace('_', ' ').title()}: {s.title}")

    return f"{competitor} shows {len(signals)} signal(s) this period. " + "; ".join(parts)


def _build_signal_breakdown(signals: List[Signal]) -> Dict[str, int]:
    """Build a breakdown of signals by type and severity."""
    breakdown: Dict[str, int] = {}
    for s in signals:
        type_key = s.type.value
        sev_key = s.severity.value
        breakdown[f"{type_key}_total"] = breakdown.get(f"{type_key}_total", 0) + 1
        breakdown[f"{type_key}_{sev_key}"] = breakdown.get(f"{type_key}_{sev_key}", 0) + 1
        breakdown[f"severity_{sev_key}"] = breakdown.get(f"severity_{sev_key}", 0) + 1
    return breakdown


def _build_detailed_summary(
    competitor: str,
    signals: List[Signal],
    raw_results: List[RawSearchResult],
    score: float,
    movement_level: str,
    days_back: int,
) -> str:
    """Build a comprehensive, detailed narrative summary for a competitor."""
    if not signals and not raw_results:
        return (
            f"No competitive activity detected for {competitor} in the past {days_back} days. "
            f"The competitor shows no significant movement across news, web, or job sources. "
            f"Score: {score} | Movement Level: {movement_level}."
        )

    parts: List[str] = []

    # Overview
    parts.append(f"## Competitive Intelligence Report: {competitor.upper()}")
    parts.append(f"- **Analysis Period:** Past {days_back} days")
    parts.append(f"- **Movement Score:** {score} | **Movement Level:** {movement_level.upper()}")
    parts.append(f"- **Signals Detected:** {len(signals)} | **Raw Results Collected:** {len(raw_results)}")

    # Signal breakdown
    if signals:
        breakdown = _build_signal_breakdown(signals)
        type_counts = {
            k.replace("_total", ""): v
            for k, v in breakdown.items()
            if k.endswith("_total")
        }
        sev_counts = {
            k.replace("severity_", ""): v
            for k, v in breakdown.items()
            if k.startswith("severity_")
        }

        type_str = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))
        sev_str = ", ".join(f"{k}: {v}" for k, v in sorted(sev_counts.items()))
        parts.append("")
        parts.append("### Signal Breakdown")
        parts.append(f"- **By Type:** {type_str}")
        parts.append(f"- **By Severity:** {sev_str}")

    # High-severity signals (most important)
    high_signals = [s for s in signals if s.severity == Severity.HIGH]
    if high_signals:
        parts.append("")
        parts.append("### High-Severity Signals (Priority Attention)")
        for s in high_signals:
            parts.append(f"- **[{s.type.value.replace('_', ' ').title()}]** {s.title}")
            parts.append(f"  - Source: {s.source} | Date: {s.date or 'N/A'}")
            parts.append(f"  - Description: {s.description}")
            parts.append(f"  - URL: {s.url or 'N/A'}")

    # Medium-severity signals
    medium_signals = [s for s in signals if s.severity == Severity.MEDIUM]
    if medium_signals:
        parts.append("")
        parts.append("### Medium-Severity Signals")
        for s in medium_signals:
            parts.append(f"- **[{s.type.value.replace('_', ' ').title()}]** {s.title}")
            parts.append(f"  - Source: {s.source} | Date: {s.date or 'N/A'}")
            parts.append(f"  - URL: {s.url or 'N/A'}")

    # Low-severity signals
    low_signals = [s for s in signals if s.severity == Severity.LOW]
    if low_signals:
        parts.append("")
        parts.append(f"### Low-Severity Signals ({len(low_signals)} detected)")
        for s in low_signals:
            parts.append(f"- [{s.type.value.replace('_', ' ').title()}] {s.title} (Source: {s.source})")

    # Strategic implications
    parts.append("")
    parts.append("### Strategic Implications")
    if score >= 10:
        parts.append(
            f"{competitor} is exhibiting **HIGH** competitive activity. "
            f"This level of movement suggests significant strategic initiatives underway, "
            f"including potential market expansion, major partnerships, or product launches. "
            f"Immediate attention and strategic response planning is recommended."
        )
    elif score >= 5:
        parts.append(
            f"{competitor} is showing **MEDIUM** competitive activity. "
            f"Monitor closely for emerging trends that could escalate. "
            f"Consider tactical adjustments to your go-to-market strategy."
        )
    elif score > 0:
        parts.append(
            f"{competitor} is showing **LOW** competitive activity. "
            f"Maintain routine monitoring. No immediate strategic response required."
        )
    else:
        parts.append(
            f"{competitor} shows no significant competitive movement. "
            f"Continue standard monitoring protocols."
        )

    # Source distribution
    source_counts: Dict[str, int] = {}
    for r in raw_results:
        source_counts[r.source] = source_counts.get(r.source, 0) + 1
    if source_counts:
        source_str = ", ".join(f"{k}: {v}" for k, v in sorted(source_counts.items()))
        parts.append("")
        parts.append(f"### Data Sources\n- {source_str}")

    return "\n".join(parts)


class RadarEngine:
    """Core engine for running competitive intelligence radar."""

    def __init__(self, client: Optional[SearchAPIClient] = None):
        self.client = client or SearchAPIClient()

    async def run(self, request: RadarRequest) -> List[CompetitorRadar]:
        """Run the radar for all competitors."""
        results: List[CompetitorRadar] = []

        for competitor in request.competitors:
            signals, raw_results, search_sources = await self._analyze_competitor(
                competitor, request.keywords, request.days_back
            )
            signals = _deduplicate(signals)
            score = _score_competitor(signals)
            movement = _movement_level(score)
            breakdown = _build_signal_breakdown(signals)
            detailed = _build_detailed_summary(
                competitor, signals, raw_results, score, movement, request.days_back
            )

            results.append(
                CompetitorRadar(
                    competitor=competitor,
                    signals=signals,
                    score=score,
                    movement_level=movement,
                    summary=_build_summary(competitor, signals),
                    detailed_summary=detailed,
                    raw_results=raw_results,
                    search_sources=search_sources,
                    signal_breakdown=breakdown,
                    total_raw_results=len(raw_results),
                )
            )

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _time_period(self, days_back: int) -> str:
        """Translate the look-back window (days) into a SearchAPI time_period value."""
        if days_back <= 1:
            return "last_day"
        if days_back <= 7:
            return "last_week"
        if days_back <= 30:
            return "last_month"
        return "last_year"

    async def _analyze_competitor(
        self, competitor: str, keywords: List[str], days_back: int
    ) -> Tuple[List[Signal], List[RawSearchResult], List[str]]:
        """Analyze a single competitor across multiple search dimensions.

        Returns a tuple of (signals, raw_results, search_sources).
        """
        signals: List[Signal] = []
        raw_results: List[RawSearchResult] = []
        search_sources: List[str] = []
        time_period = self._time_period(days_back)

        # 1. Company news (recency is handled server-side via SearchAPI time_period)
        news_results = await self.client.search_company_news(competitor, time_period=time_period)
        search_sources.append("Google News (Company)")
        for item in news_results:
            # Aggregate ALL raw results (even if not classified)
            source = _extract_source(item) or "Google News"
            date = _extract_date(item)
            if not _is_recent(date, days_back):
                continue
            raw_results.append(
                RawSearchResult(
                    source=source,
                    engine="google_news",
                    title=_extract_title(item),
                    snippet=_extract_snippet(item),
                    url=_extract_url(item),
                    date=date,
                    thumbnail=_extract_thumbnail(item),
                    position=_extract_position(item),
                    rating=_extract_rating(item),
                    metadata={
                        "competitor": competitor,
                        "search_type": "company_news",
                        **_extra_metadata(item),
                    },
                )
            )

            title = _extract_title(item)
            snippet = _extract_snippet(item)
            if not title and not snippet:
                continue
            signal_type, severity = _classify_signal(title, snippet, source)
            signals.append(
                Signal(
                    competitor=competitor,
                    type=signal_type,
                    severity=severity,
                    title=title or snippet,
                    description=snippet,
                    url=_extract_url(item),
                    source=source,
                    date=date,
                )
            )

        # 2. Company web presence (SEO movement)
        web_results = await self.client.search_company_web(competitor, time_period=time_period)
        search_sources.append("Google Web (Company)")
        for item in web_results:
            # Aggregate ALL raw results
            source = _extract_source(item) or "Web Search"
            date = _extract_date(item)
            if not _is_recent(date, days_back):
                continue
            raw_results.append(
                RawSearchResult(
                    source=source,
                    engine="google",
                    title=_extract_title(item),
                    snippet=_extract_snippet(item),
                    url=_extract_url(item),
                    date=date,
                    thumbnail=_extract_thumbnail(item),
                    position=_extract_position(item),
                    rating=_extract_rating(item),
                    metadata={
                        "competitor": competitor,
                        "search_type": "company_web",
                        **_extra_metadata(item),
                    },
                )
            )

            title = _extract_title(item)
            snippet = _extract_snippet(item)
            if not title and not snippet:
                continue
            signal_type, severity = _classify_signal(title, snippet, source)
            if signal_type == SignalType.NEWS_ACTIVITY:
                continue  # Skip generic web results from signals (but keep in raw_results)
            signals.append(
                Signal(
                    competitor=competitor,
                    type=signal_type,
                    severity=severity,
                    title=title or snippet,
                    description=snippet,
                    url=_extract_url(item),
                    source=source,
                    date=date,
                )
            )

        # 3. Job postings (leverage structured fields: location, salary, posted date)
        job_results = await self.client.search_company_jobs(competitor)
        search_sources.append("Google Jobs (Company)")
        job_locations: set = set()
        job_salaries: List[str] = []
        for item in job_results:
            # Aggregate ALL raw job results
            source = _extract_source(item) or "Google Jobs"
            details = _extract_job_details(item)
            date = details.get("posted_at") or _extract_date(item)
            if not _is_recent(date, days_back):
                continue
            if details.get("location"):
                job_locations.add(details["location"])
            if details.get("salary"):
                job_salaries.append(details["salary"])
            raw_results.append(
                RawSearchResult(
                    source=source,
                    engine="google_jobs",
                    title=_extract_title(item),
                    snippet=_extract_snippet(item),
                    url=_extract_url(item),
                    date=date,
                    thumbnail=_extract_thumbnail(item),
                    position=_extract_position(item),
                    metadata={
                        "competitor": competitor,
                        "search_type": "company_jobs",
                        "company_name": item.get("company_name"),
                        "job_type": details.get("job_type"),
                        "salary": details.get("salary"),
                        "locations": details.get("location"),
                        **_extra_metadata(item),
                    },
                )
            )

        if job_results:
            location_str = f" Locations: {', '.join(sorted(job_locations))}." if job_locations else ""
            salary_str = f" Sample compensation: {job_salaries[0]}." if job_salaries else ""
            signals.append(
                Signal(
                    competitor=competitor,
                    type=SignalType.NEW_JOBS,
                    severity=Severity.MEDIUM,
                    title=f"{competitor} - {len(job_results)} new job postings",
                    description=(
                        f"Detected {len(job_results)} recent job postings for {competitor}."
                        f"{location_str}{salary_str}"
                    ),
                    source="Google Jobs",
                    metadata={
                        "job_count": len(job_results),
                        "locations": sorted(job_locations),
                        "salaries": job_salaries[:5],
                    },
                )
            )

        # 4. Keyword-specific news (industry signals; recency via SearchAPI time_period)
        for keyword in keywords:
            keyword_results = await self.client.search_keyword_news(keyword, time_period=time_period)
            search_sources.append(f"Google News (Keyword: {keyword})")
            for item in keyword_results:
                # Aggregate ALL raw results
                date = _extract_date(item)
                if not _is_recent(date, days_back):
                    continue
                raw_results.append(
                    RawSearchResult(
                        source=_extract_source(item) or f"Keyword: {keyword}",
                        engine="google_news",
                        title=_extract_title(item),
                        snippet=_extract_snippet(item),
                        url=_extract_url(item),
                        date=date,
                        metadata={
                            "competitor": competitor,
                            "search_type": "keyword_news",
                            "keyword": keyword,
                        },
                    )
                )

                title = _extract_title(item)
                snippet = _extract_snippet(item)
                if not title and not snippet:
                    continue
                # Only include if the competitor is mentioned
                combined = f"{title} {snippet}".lower()
                if competitor.lower() not in combined:
                    continue
                signal_type, severity = _classify_signal(title, snippet, _extract_source(item) or "keyword")
                signals.append(
                    Signal(
                        competitor=competitor,
                        type=signal_type,
                        severity=severity,
                        title=title or snippet,
                        description=snippet,
                        url=_extract_url(item),
                        source=f"Keyword: {keyword}",
                        date=date,
                        metadata={"keyword": keyword},
                    )
                )

        return signals, raw_results, search_sources
