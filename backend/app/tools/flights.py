"""Real flight search via Duffel (test mode).

POST /air/offer_requests?return_offers=true with slices + passengers. In test
mode, results come back as "Duffel Airways" (IATA ZZ) with synthetic prices —
that's expected sandbox behavior, not a bug. PVD->RAI is a known zero-offer
route in Duffel's sandbox, useful for testing the empty-result path.
"""

import logging

import httpx

from app.tools import cache, duffel_client

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60 * 60 * 6  # 6h: flight offers go stale fast, but protect quota for retries


def _normalize(raw: dict) -> list[dict]:
    offers = []
    for offer in raw.get("data", {}).get("offers", []):
        segments = []
        stops = 0
        outbound_segment_count = 0
        slices = offer.get("slices", [])
        for slice_index, slice_ in enumerate(slices):
            slice_segments = slice_.get("segments", [])
            stops += max(len(slice_segments) - 1, 0)
            if slice_index == 0:
                outbound_segment_count = len(slice_segments)
            for seg in slice_segments:
                segments.append(
                    {
                        "carrier": seg.get("operating_carrier", {}).get("iata_code"),
                        "flight_number": seg.get("operating_carrier_flight_number")
                        or seg.get("marketing_carrier_flight_number"),
                        "from": seg.get("origin", {}).get("iata_code"),
                        "to": seg.get("destination", {}).get("iata_code"),
                        "departure_at": seg.get("departing_at"),
                        "arrival_at": seg.get("arriving_at"),
                    }
                )
        first_slice = slices[0] if slices else {}
        # For round trips, `segments` flattens BOTH the outbound and return legs —
        # so "first segment's origin, last segment's destination" would land back
        # at the origin. Derive the displayable origin/destination from the
        # outbound slice only.
        outbound_segments = segments[:outbound_segment_count]
        offers.append(
            {
                "offer_id": offer.get("id"),
                "carrier": segments[0]["carrier"] if segments else None,
                "price": float(offer["total_amount"]),
                "currency": offer.get("total_currency"),
                "stops": stops,
                "duration": first_slice.get("duration"),
                "origin": outbound_segments[0]["from"] if outbound_segments else None,
                "destination": outbound_segments[-1]["to"] if outbound_segments else None,
                "segments": segments,
            }
        )
    return offers


def search(
    origin: str,
    destination: str,
    depart: str,
    return_: str | None = None,
    adults: int = 1,
) -> list[dict]:
    """origin/destination: IATA codes (e.g. 'JFK'). depart/return_: 'YYYY-MM-DD'.
    Returns [] on any failure or zero results — never raises."""
    params = {
        "origin": origin,
        "destination": destination,
        "depart": depart,
        "return_": return_,
        "adults": adults,
    }

    def compute() -> list[dict]:
        slices = [{"origin": origin, "destination": destination, "departure_date": depart}]
        if return_:
            slices.append({"origin": destination, "destination": origin, "departure_date": return_})
        body = {
            "data": {
                "slices": slices,
                "passengers": [{"type": "adult"} for _ in range(adults)],
                "cabin_class": "economy",
            }
        }
        try:
            raw = duffel_client.post("/air/offer_requests", body, params={"return_offers": "true"})
            return _normalize(raw)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("flights.search failed for %s->%s on %s: %s", origin, destination, depart, exc)
            return []

    return cache.get_or_set("flights", params, CACHE_TTL_SECONDS, compute)
