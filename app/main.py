import os
from datetime import datetime
from typing import List, Optional
import logging

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .schemas import RadarRequest, RadarResponse, CompetitorRadar
from .radar import RadarEngine
from .ai_summary import AISummaryGenerator
from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Competitive Intelligence Radar",
    description="Track competitor movements using SearchAPI.io",
    version="1.0.0",
)

# CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for frontend
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_radar_engine() -> RadarEngine:
    """Dependency to get the radar engine instance."""
    try:
        return RadarEngine()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Serve the frontend UI."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "Competitive Intelligence Radar API",
        "docs": "/docs",
        "endpoints": ["/api/radar", "/api/health"],
    }


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "searchapi_configured": bool(settings.searchapi_api_key),
        "openai_configured": bool(settings.openai_api_key),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/radar", response_model=RadarResponse)
async def run_radar(
    request: RadarRequest,
    engine: RadarEngine = Depends(get_radar_engine),
):
    """Run the competitive intelligence radar."""
    try:
        logger.info(
            f"Running radar for {len(request.competitors)} competitors "
            f"with {len(request.keywords)} keywords"
        )

        # Run the radar engine
        competitors = await engine.run(request)

        # Generate AI executive summary (concise)
        summary_generator = AISummaryGenerator()
        ai_summary = await summary_generator.generate(
            competitors, keywords=request.keywords, days_back=request.days_back
        )

        # Generate detailed AI executive summary
        detailed_ai_summary = await summary_generator.generate_detailed(
            competitors, keywords=request.keywords, days_back=request.days_back
        )

        total_signals = sum(len(c.signals) for c in competitors)
        total_raw_results = sum(c.total_raw_results for c in competitors)

        # Build search metadata
        all_sources = set()
        for c in competitors:
            all_sources.update(c.search_sources)

        search_metadata = {
            "competitors_tracked": len(request.competitors),
            "keywords_monitored": len(request.keywords),
            "days_back": request.days_back,
            "search_sources": sorted(all_sources),
            "total_competitors_with_signals": sum(1 for c in competitors if c.signals),
        }

        return RadarResponse(
            competitors=competitors,
            ai_executive_summary=ai_summary,
            detailed_ai_summary=detailed_ai_summary,
            generated_at=datetime.utcnow().isoformat(),
            total_signals=total_signals,
            total_raw_results=total_raw_results,
            search_metadata=search_metadata,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Radar execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Radar execution failed: {str(e)}")


@app.get("/api/radar", response_model=RadarResponse)
async def run_radar_get(
    competitors: Optional[str] = Query(
        None, description="Comma-separated list of competitors"
    ),
    keywords: Optional[str] = Query(
        None, description="Comma-separated list of keywords"
    ),
    days_back: int = Query(settings.default_days_back, ge=1, le=30),
    engine: RadarEngine = Depends(get_radar_engine),
):
    """Run the competitive intelligence radar via GET request."""
    comp_list = (
        [c.strip() for c in competitors.split(",") if c.strip()]
        if competitors
        else None
    )
    kw_list = (
        [k.strip() for k in keywords.split(",") if k.strip()]
        if keywords
        else None
    )

    request = RadarRequest(
        competitors=comp_list or RadarRequest().competitors,
        keywords=kw_list or RadarRequest().keywords,
        days_back=days_back,
    )
    return await run_radar(request, engine)
