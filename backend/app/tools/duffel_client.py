"""Shared Duffel API client, used by flights.py and stays.py.

Single bearer token (the token itself decides test vs live — `duffel_test_...`
keeps everything in sandbox). Every request needs the Duffel-Version header.
"""

import httpx

from app.config import get_settings

TIMEOUT_SECONDS = 15.0
DUFFEL_VERSION = "v2"


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.duffel_api_key}",
        "Duffel-Version": DUFFEL_VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def post(path: str, body: dict, params: dict | None = None) -> dict:
    """POST a Duffel API path with auth headers. Raises on HTTP errors."""
    settings = get_settings()
    response = httpx.post(
        f"{settings.duffel_base_url}{path}",
        json=body,
        params=params,
        headers=_headers(),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
