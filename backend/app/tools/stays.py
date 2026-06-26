"""Hotel search, backed by OpenStreetMap lodging POIs (tourism=hotel).

Duffel Stays requires a sales-enabled account (403 "feature not enabled" on
a plain test token), so hotels come from the free, no-key places tool
instead. Trade-off: real names and locations, but no live pricing — the
planner/budget nodes treat hotel cost as an estimate, not a quoted rate.
"""

from app.tools import places


def search(city: str, checkin: str, checkout: str, adults: int = 1) -> list[dict]:
    """city: free-text place name (e.g. 'Paris, France'). checkin/checkout: 'YYYY-MM-DD'.
    Returns [] on any failure or zero results — never raises (places.search already
    guarantees this)."""
    pois = places.search(city, ["hotel", "hostel", "guest_house"])
    return [
        {
            "hotel_id": poi["osm_id"],
            "name": poi["name"],
            "lat": poi["lat"],
            "lon": poi["lon"],
            "checkin": checkin,
            "checkout": checkout,
            "price": None,
            "currency": None,
        }
        for poi in pois
    ]
