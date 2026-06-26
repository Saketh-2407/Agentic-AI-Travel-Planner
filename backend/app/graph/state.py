"""Graph state + the Pydantic schemas used for structured LLM output."""

import operator
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field


class ParsedTrip(BaseModel):
    """What the parser node extracts from the raw query (+ memory, in Phase 3)."""

    origin: str | None = None
    destinations: list[str] = Field(default_factory=list)  # IATA codes, for flight search
    destination_names: list[str] = Field(default_factory=list)  # human-readable, same order, for geocoding
    start_date: str | None = None  # YYYY-MM-DD
    end_date: str | None = None
    travelers: int = 1
    budget: float | None = None
    currency: str = "USD"
    interests: list[str] = Field(default_factory=list)
    pace: Literal["relaxed", "moderate", "packed"] | None = None
    constraints: list[str] = Field(default_factory=list)
    intent: Literal["full_trip", "flights_only", "stays_only", "activities_only"] = "full_trip"
    needs_clarification: bool = False
    clarify_question: str | None = None


ActivitySlot = Literal[
    "sight", "viewpoint", "museum", "park", "cafe", "food", "bar", "activity", "market", "historic"
]


class ItineraryActivity(BaseModel):
    name: str
    slot: ActivitySlot
    note: str = ""  # one short, grounded line — no invented facts about the place


class ItineraryDay(BaseModel):
    day_number: int
    date: str
    theme: str  # short evocative day title, e.g. "Gothic Quarter & waterfront"
    area: str  # the neighborhood/area this day is centered on
    activities: list[ItineraryActivity] = Field(default_factory=list)  # 3-7, ordered morning->evening
    suggested_hotel: str | None = None  # must exactly match a retrieved stay's name
    weather_note: str | None = None


class ItineraryPlan(BaseModel):
    """The planner's structured output. Budget math is computed deterministically
    in code from tool data, not by the LLM — this is just the narrative shape,
    grounded in the flight/hotel/activity options actually retrieved."""

    flight_offer_id: str | None = None
    hotel_id: str | None = None
    days: list[ItineraryDay] = Field(default_factory=list)


class CriticVerdict(BaseModel):
    passed: bool
    groundedness_ok: bool
    budget_ok: bool
    day_balance_ok: bool
    variety_ok: bool = True
    issues: list[str] = Field(default_factory=list)


class FinalizerSummary(BaseModel):
    """A grounded, readable narration of the already-validated structured plan —
    restates real data only, never invents flights/hotels/places/facts."""

    overview: str
    flights_section: str
    stays_section: str
    itinerary_section: str
    budget_section: str
    closing_summary: str


class TravelState(TypedDict, total=False):
    user_id: str | None
    trip_id: str | None
    thread_id: str
    messages: Annotated[list[dict], operator.add]
    raw_query: str
    parsed: dict[str, Any]
    needs_clarification: bool
    clarify_question: str | None
    route: list[str]
    flights: list[dict]
    stays: list[dict]
    activities: list[dict]
    weather: list[dict]
    itinerary: list[dict]
    selected_flight_offer_id: str | None
    selected_hotel_id: str | None
    budget_breakdown: dict[str, Any]
    critic_verdict: dict[str, Any]
    revision_count: int
    llm_calls: int
    llm_usage: dict[str, Any]  # running token/cost totals + per-call breadcrumbs, see nodes._accumulate_usage
    narrative_summary: dict[str, Any]
    final: dict[str, Any]
