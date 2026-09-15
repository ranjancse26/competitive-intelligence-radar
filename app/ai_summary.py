import json
import logging
from typing import List, Optional

from .schemas import CompetitorRadar
from .config import settings

logger = logging.getLogger(__name__)


class AISummaryGenerator:
    """Generates AI executive summaries of competitive radar results."""

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model

    async def generate(
        self,
        competitors: List[CompetitorRadar],
        keywords: Optional[List[str]] = None,
        days_back: Optional[int] = None,
    ) -> str:
        """Generate an executive summary using OpenAI or fall back to rule-based."""
        if self.api_key:
            try:
                return await self._generate_with_openai(competitors, keywords, days_back)
            except Exception as e:
                logger.warning(f"OpenAI summary failed, using rule-based: {e}")

        return self._generate_rule_based(competitors, keywords, days_back)

    async def generate_detailed(
        self,
        competitors: List[CompetitorRadar],
        keywords: Optional[List[str]] = None,
        days_back: Optional[int] = None,
    ) -> str:
        """Generate a detailed, multi-paragraph executive summary using OpenAI or rule-based fallback."""
        if self.api_key:
            try:
                return await self._generate_detailed_with_openai(competitors, keywords, days_back)
            except Exception as e:
                logger.warning(f"OpenAI detailed summary failed, using rule-based: {e}")

        return self._generate_detailed_rule_based(competitors, keywords, days_back)

    def _monitoring_context(self, competitors, keywords, days_back):
        """Resolve the effective monitored scope, falling back to config/defaults.json."""
        kw = keywords or settings.default_keywords or []
        db = days_back or settings.default_days_back
        comps = [c.competitor for c in competitors] or list(settings.default_competitors)
        return comps, kw, db

    def _monitoring_block(self, competitors, keywords, days_back) -> str:
        """Human-readable monitoring configuration for inclusion in prompts."""
        comps, kw, db = self._monitoring_context(competitors, keywords, days_back)
        return "\n".join([
            "MONITORING CONFIGURATION (from config/defaults.json):",
            f"- Tracked competitors: {', '.join(comps) if comps else 'N/A'}",
            f"- Monitored keywords: {', '.join(kw) if kw else 'N/A'}",
            f"- Lookback window: past {db} days",
        ])

    async def _generate_with_openai(
        self,
        competitors: List[CompetitorRadar],
        keywords: Optional[List[str]] = None,
        days_back: Optional[int] = None,
    ) -> str:
        """Generate summary using OpenAI API."""
        import httpx

        # Build a compact representation of the radar data
        radar_data = []
        for comp in competitors:
            signals = [
                {
                    "type": s.type.value,
                    "severity": s.severity.value,
                    "title": s.title,
                    "description": s.description,
                }
                for s in comp.signals
            ]
            radar_data.append(
                {
                    "competitor": comp.competitor,
                    "score": comp.score,
                    "movement_level": comp.movement_level,
                    "signal_count": len(comp.signals),
                    "signals": signals,
                }
            )

        prompt = f"""You are a competitive intelligence analyst. Based on the following competitive radar data, write a concise executive summary (2-4 sentences) highlighting the most important competitive movements.

Focus on:
1. Which competitor shows the strongest movement and why
2. Key strategic signals (announcements, partnerships, acquisitions)
3. Notable hiring or product activity
4. Any industry trends from the keywords

{self._monitoring_block(competitors, keywords, days_back)}

Radar data:
{json.dumps(radar_data, indent=2)}

Write the summary in a professional, analytical tone. Start with the strongest competitor."""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a competitive intelligence analyst writing executive summaries.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 2000,
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _generate_detailed_with_openai(
        self,
        competitors: List[CompetitorRadar],
        keywords: Optional[List[str]] = None,
        days_back: Optional[int] = None,
    ) -> str:
        """Generate a detailed, multi-paragraph executive summary using OpenAI API."""
        import httpx

        # Build a comprehensive representation of the radar data including raw results
        radar_data = []
        for comp in competitors:
            signals = [
                {
                    "type": s.type.value,
                    "severity": s.severity.value,
                    "title": s.title,
                    "description": s.description,
                    "url": s.url,
                    "source": s.source,
                    "date": s.date,
                }
                for s in comp.signals
            ]
            raw_results = [
                {
                    "source": r.source,
                    "engine": r.engine,
                    "title": r.title,
                    "snippet": r.snippet,
                    "url": r.url,
                    "date": r.date,
                }
                for r in comp.raw_results
            ]
            radar_data.append(
                {
                    "competitor": comp.competitor,
                    "score": comp.score,
                    "movement_level": comp.movement_level,
                    "signal_count": len(comp.signals),
                    "raw_result_count": len(comp.raw_results),
                    "signal_breakdown": comp.signal_breakdown,
                    "search_sources": comp.search_sources,
                    "signals": signals,
                    "raw_results": raw_results,
                }
            )

        prompt = f"""You are a senior competitive intelligence analyst. Based on the following comprehensive competitive radar data, write a detailed, multi-paragraph executive summary (4-6 paragraphs) that provides a thorough analysis of the competitive landscape.

{self._monitoring_block(competitors, keywords, days_back)}

Your analysis should include:

1. **Executive Overview** — A high-level summary of the overall competitive landscape, which competitor is most active, and the key themes emerging across the tracked companies.

2. **Competitor Deep-Dive** — For each competitor (in order of movement score), provide a detailed analysis of their detected signals, including:
   - What types of signals were detected (acquisitions, partnerships, product launches, hiring, pricing, regulatory, SEO)
   - The severity and strategic importance of each signal
   - Specific details from the signal titles and descriptions
   - Source attribution (which search engine/source the signal came from)

3. **Signal Categorization** — Group all detected signals by type and severity across all competitors. Highlight the most significant high-severity signals (acquisitions, partnerships, strategic announcements) and explain their potential market impact.

4. **Industry Trends** — Analyze the keyword-based signals to identify broader industry trends. What themes are emerging across the market? How are different competitors responding to these trends?

5. **Strategic Implications & Recommendations** — Based on the aggregated data, provide actionable recommendations. Which competitor movements pose the greatest threat or opportunity? What strategic responses should be considered?

6. **Data Coverage Summary** — Report on the total number of raw search results collected, the sources queried, and the signal-to-result ratio for each competitor.

Radar data:
{json.dumps(radar_data, indent=2)}

Write in a professional, analytical tone suitable for executive leadership. Be specific and reference actual signal details, titles, and sources from the data. Do not generalize — cite concrete evidence from the results."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a senior competitive intelligence analyst writing detailed executive summaries for leadership. You provide thorough, data-driven analysis with specific references to source material.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 4000,
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    def _generate_rule_based(
        self,
        competitors: List[CompetitorRadar],
        keywords: Optional[List[str]] = None,
        days_back: Optional[int] = None,
    ) -> str:
        """Generate a summary using rule-based logic (no external API needed)."""
        if not competitors:
            return "No competitive data available for analysis."

        _, kw, _ = self._monitoring_context(competitors, keywords, days_back)

        # Find the strongest competitor
        top = competitors[0]
        if top.score == 0:
            base = (
                "No significant competitive movement detected across the tracked "
                "competitors this period. All monitored companies show stable activity."
            )
            return f"{base} Monitored keywords: {', '.join(kw) if kw else 'N/A'}." if kw else base

        # Build the summary
        parts = []

        # Top competitor
        top_signals = top.signals
        signal_desc = []
        for s in top_signals:
            signal_desc.append(s.type.value.replace("_", " "))

        if signal_desc:
            parts.append(
                f"{top.competitor} shows the strongest competitive movement this "
                f"period, driven by {', '.join(signal_desc)} activity"
            )
        else:
            parts.append(
                f"{top.competitor} shows the strongest competitive movement this period"
            )

        # Second competitor if significant
        if len(competitors) > 1 and competitors[1].score > 0:
            second = competitors[1]
            second_signals = second.signals[:1]
            if second_signals:
                parts.append(
                    f"followed by {second.competitor} with "
                    f"{second_signals[0].type.value.replace('_', ' ')} activity"
                )

        # Total signals
        total_signals = sum(len(c.signals) for c in competitors)
        active_competitors = sum(1 for c in competitors if c.score > 0)
        parts.append(
            f"Across {active_competitors} of {len(competitors)} tracked competitors, "
            f"{total_signals} competitive signals were detected"
        )

        # Notable signals
        notable = []
        for comp in competitors:
            for s in comp.signals:
                if s.severity.value == "high":
                    notable.append(f"{comp.competitor}: {s.title}")
        if notable:
            parts.append("Key highlights include " + "; ".join(notable))

        return ". ".join(parts) + "."

    def _generate_detailed_rule_based(
        self,
        competitors: List[CompetitorRadar],
        keywords: Optional[List[str]] = None,
        days_back: Optional[int] = None,
    ) -> str:
        """Generate a detailed, multi-section summary using rule-based logic (no external API needed)."""
        if not competitors:
            return "No competitive data available for analysis."

        comps, kw, db = self._monitoring_context(competitors, keywords, days_back)

        total_signals = sum(len(c.signals) for c in competitors)
        total_raw = sum(c.total_raw_results for c in competitors)
        active_competitors = sum(1 for c in competitors if c.score > 0)

        parts: List[str] = []

        # Monitoring configuration (from config/defaults.json)
        parts.append("=" * 70)
        parts.append("DETAILED COMPETITIVE INTELLIGENCE ANALYSIS")
        parts.append("=" * 70)
        parts.append("")
        parts.append("MONITORING CONFIGURATION (config/defaults.json)")
        parts.append(f"  Tracked Competitors: {', '.join(comps) if comps else 'N/A'}")
        parts.append(f"  Monitored Keywords: {', '.join(kw) if kw else 'N/A'}")
        parts.append(f"  Lookback Window: past {db} days")
        parts.append("")

        # 1. Executive Overview
        parts.append("1. EXECUTIVE OVERVIEW")
        parts.append("-" * 40)
        if total_signals == 0:
            parts.append(
                "No significant competitive movement was detected across the tracked "
                "competitors during this analysis period. All monitored companies show "
                "stable activity with no high-priority signals."
            )
        else:
            top = competitors[0]
            parts.append(
                f"Analysis of {len(competitors)} competitors over the configured look-back "
                f"window detected {total_signals} competitive signals from {total_raw} "
                f"aggregated raw search results. {active_competitors} of {len(competitors)} "
                f"competitors showed measurable activity."
            )
            parts.append("")
            parts.append(
                f"The most active competitor is {top.competitor} with a movement score of "
                f"{top.score} ({top.movement_level.upper()} movement level), driven by "
                f"{len(top.signals)} detected signals."
            )

        # 2. Competitor Deep-Dive
        parts.append("")
        parts.append("2. COMPETITOR DEEP-DIVE")
        parts.append("-" * 40)
        for comp in competitors:
            parts.append(f"\n  {comp.competitor} (Score: {comp.score} | Movement: {comp.movement_level.upper()})")
            parts.append(f"  Signals: {len(comp.signals)} | Raw Results: {comp.total_raw_results}")

            if comp.signal_breakdown:
                parts.append(f"  Signal Breakdown:")
                for key, val in sorted(comp.signal_breakdown.items()):
                    parts.append(f"    - {key}: {val} ")

            if comp.signals:
                parts.append(f"  Detected Signals:")
                for s in comp.signals:
                    parts.append(
                        f"    [{s.severity.value.upper()}] {s.type.value.replace('_', ' ').title()}: "
                        f"{s.title}"
                    )
                    if s.description:
                        parts.append(f"      Description: {s.description}")
                    if s.url:
                        parts.append(f"      URL: {s.url}")
                    parts.append(f"      Source: {s.source}")
                    if s.date:
                        parts.append(f"      Date: {s.date}")
            else:
                parts.append("  No classified signals detected.")

            if comp.search_sources:
                parts.append(f"  Search Sources Queried: {', '.join(comp.search_sources)}")

        # 3. Signal Categorization
        parts.append("")
        parts.append("3. SIGNAL CATEGORIZATION")
        parts.append("-" * 40)
        high_signals = []
        medium_signals = []
        low_signals = []
        for comp in competitors:
            for s in comp.signals:
                if s.severity == "high":
                    high_signals.append((comp.competitor, s))
                elif s.severity == "medium":
                    medium_signals.append((comp.competitor, s))
                else:
                    low_signals.append((comp.competitor, s))

        if high_signals:
            parts.append(f"\n  HIGH-SEVERITY SIGNALS ({len(high_signals)} total):")
            for comp_name, s in high_signals:
                parts.append(
                    f"    • {comp_name}: [{s.type.value.replace('_', ' ').title()}] {s.title}"
                )
                if s.url:
                    parts.append(f"      URL: {s.url}")
        else:
            parts.append("\n  No high-severity signals detected.")

        if medium_signals:
            parts.append(f"\n  MEDIUM-SEVERITY SIGNALS ({len(medium_signals)} total):")
            for comp_name, s in medium_signals:
                parts.append(
                    f"    • {comp_name}: [{s.type.value.replace('_', ' ').title()}] {s.title}"
                )

        if low_signals:
            parts.append(f"\n  LOW-SEVERITY SIGNALS ({len(low_signals)} total):")
            for comp_name, s in low_signals:
                parts.append(
                    f"    • {comp_name}: [{s.type.value.replace('_', ' ').title()}] {s.title}"
                )

        # 4. Strategic Implications
        parts.append("")
        parts.append("4. STRATEGIC IMPLICATIONS")
        parts.append("-" * 40)
        for comp in competitors:
            if comp.score >= 10:
                parts.append(
                    f"\n  {comp.competitor} (HIGH activity): Exhibiting significant strategic "
                    f"initiatives. Immediate attention and strategic response planning recommended."
                )
            elif comp.score >= 5:
                parts.append(
                    f"\n  {comp.competitor} (MEDIUM activity): Monitor closely for emerging "
                    f"trends that could escalate. Consider tactical adjustments."
                )
            elif comp.score > 0:
                parts.append(
                    f"\n  {comp.competitor} (LOW activity): Maintain routine monitoring."
                )
            else:
                parts.append(
                    f"\n  {comp.competitor} (NO activity): No significant movement detected."
                )

        # 5. Data Coverage Summary
        parts.append("")
        parts.append("5. DATA COVERAGE SUMMARY")
        parts.append("-" * 40)
        parts.append(f"\n  Total Competitors Analyzed: {len(competitors)}")
        parts.append(f"  Total Signals Detected: {total_signals}")
        parts.append(f"  Total Raw Results Aggregated: {total_raw}")
        parts.append(f"  Active Competitors: {active_competitors}")
        if total_raw > 0:
            ratio = total_signals / total_raw * 100
            parts.append(f"  Signal-to-Raw-Result Ratio: {ratio:.1f}%")
        parts.append(f"\n  Per-Competitor Raw Result Counts:")
        for comp in competitors:
            parts.append(f"    {comp.competitor}: {comp.total_raw_results} raw results, {len(comp.signals)} signals")

        parts.append("")
        parts.append("=" * 70)
        parts.append("END OF DETAILED ANALYSIS")
        parts.append("=" * 70)

        return "\n".join(parts)
