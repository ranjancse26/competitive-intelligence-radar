import httpx
from typing import List, Dict, Any, Optional
import logging

from .config import settings

logger = logging.getLogger(__name__)


class SearchAPIClient:
    """Client for interacting with the SearchAPI.io API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.searchapi_api_key
        if not self.api_key:
            raise ValueError(
                "SearchAPI.io API key is required. Set SEARCHAPI_API_KEY in your .env file."
            )

    async def _search(
        self,
        engine: str,
        query: str,
        num: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Perform a search against the SearchAPI.io API."""
        if num is None:
            num = settings.search_num
        params = {
            "engine": engine,
            "api_key": self.api_key,
            "q": query,
            "num": num,
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(settings.searchapi_base_url, params=params)
            response.raise_for_status()
            return response.json()

    async def search_news(
        self, query: str, num: Optional[int] = None, time_period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for news articles related to a query.

        `time_period` is forwarded to SearchAPI (e.g. "last_day", "last_week",
        "last_month", "last_year") so only recent results are returned server-side
        instead of filtering locally.
        """
        if num is None:
            num = settings.search_num
        kwargs = {}
        if time_period:
            kwargs["time_period"] = time_period
        try:
            data = await self._search(
                engine="google_news",
                query=query,
                num=num,
                **kwargs,
            )
            return data.get("news_results", [])
        except Exception as e:
            logger.warning(f"News search failed for '{query}': {e}")
            return []

    async def search_web(
        self, query: str, num: Optional[int] = None, time_period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform a general web search."""
        if num is None:
            num = settings.search_num
        kwargs = {}
        if time_period:
            kwargs["time_period"] = time_period
        try:
            data = await self._search(
                engine="google",
                query=query,
                num=num,
                **kwargs,
            )
            return data.get("organic_results", [])
        except Exception as e:
            logger.warning(f"Web search failed for '{query}': {e}")
            return []

    async def search_jobs(
        self, query: str, num: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search for job postings related to a company."""
        if num is None:
            num = settings.search_num
        try:
            data = await self._search(
                engine="google_jobs",
                query=query,
                num=num,
            )
            return data.get("jobs_results", [])
        except Exception as e:
            logger.warning(f"Jobs search failed for '{query}': {e}")
            return []

    async def search_company_news(
        self, company: str, num: Optional[int] = None, time_period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for news specifically about a company."""
        query = f"{company} news"
        return await self.search_news(query, num=num, time_period=time_period)

    async def search_company_web(
        self, company: str, num: Optional[int] = None, time_period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search the web for company-related content."""
        query = f"{company}"
        return await self.search_web(query, num=num, time_period=time_period)

    async def search_company_jobs(
        self, company: str, num: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search for job postings at a company."""
        query = f"{company} jobs"
        return await self.search_jobs(query, num=num)

    async def search_keyword_news(
        self, keyword: str, num: Optional[int] = None, time_period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for news related to a specific keyword."""
        return await self.search_news(keyword, num=num, time_period=time_period)
