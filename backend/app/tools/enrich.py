"""Web enrichment via Tavily — "things to do" descriptions, free-tier search."""

import logging

import httpx

from app.config import get_settings
from app.tools import cache

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT_SECONDS = 15.0
CACHE_TTL_SECONDS = 60 * 60 * 24 * 3
MAX_RESULTS = 5


def _normalize(raw: dict) -> list[dict]:
    return [
        {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content")}
        for r in raw.get("results", [])
    ]


def web(query: str) -> list[dict]:
    """Returns [] on any failure or empty results — never raises."""
    params = {"query": query}

    def compute() -> list[dict]:
        settings = get_settings()
        if not settings.tavily_api_key:
            logger.warning("enrich.web called without TAVILY_API_KEY set")
            return []
        try:
            response = httpx.post(
                TAVILY_URL,
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": MAX_RESULTS,
                    "search_depth": "basic",
                },
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return _normalize(response.json())
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("enrich.web failed for %r: %s", query, exc)
            return []

    return cache.get_or_set("enrich", params, CACHE_TTL_SECONDS, compute)
