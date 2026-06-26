"""Places of interest via OpenStreetMap: Nominatim (geocoding) + Overpass (POIs).

Both services are free with no API key, but they block or silently degrade
requests without an identifying User-Agent — so every request carries one
with a real contact email, per OSM's usage policy.
"""

import logging

import httpx

from app.config import get_settings
from app.tools import cache

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TIMEOUT_SECONDS = 20.0
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # POIs barely change; cache a week
SEARCH_RADIUS_METERS = 5000

# How many results to keep per category after fetching — keeps the planner's
# prompt small and varied (no single category, e.g. cafes, drowning out the rest)
# regardless of how many raw results Overpass returns.
MAX_PER_CATEGORY = 8
# Total raw results requested from Overpass, before per-category capping —
# needs headroom above categories_requested * MAX_PER_CATEGORY since OSM data
# density varies a lot by area and tag.
OVERPASS_RAW_LIMIT = 400

# Maps a plain-language interest to an OSM (key, value) tag. value=None means
# "key exists, any value" (e.g. historic=castle|ruins|monument|... all count).
# Unmapped categories fall back to tourism=<category>.
CATEGORY_TAGS: dict[str, tuple[str, str | None]] = {
    "attraction": ("tourism", "attraction"),
    "viewpoint": ("tourism", "viewpoint"),
    "museum": ("tourism", "museum"),
    "gallery": ("tourism", "gallery"),
    "zoo": ("tourism", "zoo"),
    "park": ("leisure", "park"),
    "cafe": ("amenity", "cafe"),
    "restaurant": ("amenity", "restaurant"),
    "bar": ("amenity", "bar"),
    "nightclub": ("amenity", "nightclub"),
    "marketplace": ("amenity", "marketplace"),
    "theatre": ("amenity", "theatre"),
    "place_of_worship": ("amenity", "place_of_worship"),
    "historic": ("historic", None),  # castle, ruins, monument, memorial, archaeological_site, ...
    "beach": ("natural", "beach"),
    "hotel": ("tourism", "hotel"),
    "hostel": ("tourism", "hostel"),
    "guest_house": ("tourism", "guest_house"),
}

# The baseline category mix the activities agent always pulls, on top of
# whatever specific interests the traveler mentioned — this is what gives the
# itinerary variety (sights + viewpoints + museums + parks + food + history)
# instead of just whatever one or two categories the user happened to name.
DEFAULT_ACTIVITY_CATEGORIES = [
    "attraction",
    "viewpoint",
    "museum",
    "gallery",
    "park",
    "cafe",
    "restaurant",
    "bar",
    "marketplace",
    "historic",
]

# Free-text interests from the parser ("good food", "museums", "shopping") rarely
# match CATEGORY_TAGS keys exactly — map common phrasings before falling back to
# a singularized lookup. Deliberately covers more than what's been hit in testing
# so far (e.g. cuisine-specific words), since the parser's free-text output is
# effectively unbounded.
CATEGORY_SYNONYMS = {
    "food": "restaurant",
    "good food": "restaurant",
    "dining": "restaurant",
    "eating": "restaurant",
    "tapas": "restaurant",
    "sushi": "restaurant",
    "pasta": "restaurant",
    "cuisine": "restaurant",
    "local food": "restaurant",
    "drinks": "bar",
    "nightlife": "nightclub",
    "live music": "nightclub",
    "clubbing": "nightclub",
    "shopping": "marketplace",
    "markets": "marketplace",
    "market": "marketplace",
    "art": "gallery",
    "art galleries": "gallery",
    "galleries": "gallery",
    "history": "historic",
    "historical": "historic",
    "historic sites": "historic",
    "nature": "park",
    "sightseeing": "attraction",
    "sights": "attraction",
    "photography": "viewpoint",
    "photo spots": "viewpoint",
    "views": "viewpoint",
    "beaches": "beach",
    "temples": "place_of_worship",
    "temple": "place_of_worship",
    "technology museums": "museum",
    "tech museums": "museum",
    "museums": "museum",
}


def _normalize_category(category: str) -> str:
    key = category.strip().lower()
    key = CATEGORY_SYNONYMS.get(key, key)
    if key not in CATEGORY_TAGS and key.endswith("s") and key[:-1] in CATEGORY_TAGS:
        key = key[:-1]
    return key


def _user_agent() -> str:
    return f"Wayfare-TravelPlanner/0.1 (contact: {get_settings().osm_contact_email})"


def geocode(area: str) -> tuple[float, float] | None:
    """Resolve a free-text place name to (lat, lon) via Nominatim. None if not found."""
    response = httpx.get(
        NOMINATIM_URL,
        params={"q": area, "format": "json", "limit": 1},
        headers={"User-Agent": _user_agent()},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def _overpass_query(lat: float, lon: float, categories: list[str]) -> str:
    clauses = []
    for category in categories:
        normalized = _normalize_category(category)
        key, value = CATEGORY_TAGS.get(normalized, ("tourism", normalized))
        if value is None:
            clauses.append(f'node["{key}"](around:{SEARCH_RADIUS_METERS},{lat},{lon});')
            clauses.append(f'way["{key}"](around:{SEARCH_RADIUS_METERS},{lat},{lon});')
        else:
            clauses.append(f'node["{key}"="{value}"](around:{SEARCH_RADIUS_METERS},{lat},{lon});')
            clauses.append(f'way["{key}"="{value}"](around:{SEARCH_RADIUS_METERS},{lat},{lon});')
    return f"[out:json][timeout:25];({''.join(clauses)});out center {OVERPASS_RAW_LIMIT};"


def _normalize(raw: dict) -> list[dict]:
    pois = []
    for element in raw.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        center = element.get("center") or {"lat": element.get("lat"), "lon": element.get("lon")}
        pois.append(
            {
                "osm_id": f"{element.get('type')}/{element.get('id')}",
                "name": name,
                "type": tags.get("tourism") or tags.get("amenity") or tags.get("leisure") or tags.get("historic"),
                "lat": center.get("lat"),
                "lon": center.get("lon"),
            }
        )
    return pois


def _cap_per_category(pois: list[dict], cap: int = MAX_PER_CATEGORY) -> list[dict]:
    """Dedupes by name (the same place often comes back as both a node and a
    way) and keeps at most `cap` results per category, so no single category
    (cafes are usually the most numerous) crowds out the rest."""
    seen_names: set[str] = set()
    counts: dict[str, int] = {}
    capped = []
    for poi in pois:
        name = poi["name"]
        if name in seen_names:
            continue
        category = poi["type"] or "other"
        if counts.get(category, 0) >= cap:
            continue
        seen_names.add(name)
        counts[category] = counts.get(category, 0) + 1
        capped.append(poi)
    return capped


def search(area: str, categories: list[str]) -> list[dict]:
    """area: free-text place name (e.g. 'Paris, France'). categories: interests
    like ['museum', 'restaurant']. Returns a deduped, per-category-capped list
    (see MAX_PER_CATEGORY). Returns [] on any failure — never raises."""
    params = {"area": area, "categories": sorted(categories)}

    def compute() -> list[dict]:
        try:
            coords = geocode(area)
            if coords is None:
                return []
            lat, lon = coords
            response = httpx.post(
                OVERPASS_URL,
                data={"data": _overpass_query(lat, lon, categories)},
                headers={"User-Agent": _user_agent()},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return _cap_per_category(_normalize(response.json()))
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("places.search failed for %s %s: %s", area, categories, exc)
            return []

    return cache.get_or_set("places", params, CACHE_TTL_SECONDS, compute)
