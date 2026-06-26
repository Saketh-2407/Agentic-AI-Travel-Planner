"""All graph node functions: parser, supervisor, the three tool-calling agents,
planner, critic, finalizer. Each takes the full TravelState and returns a
partial-state dict that LangGraph merges in.
"""

import functools
import json
import logging
import time
from datetime import date, timedelta

from langgraph.types import interrupt

from app import llm, memory
from app.graph import prompts
from app.graph.state import CriticVerdict, FinalizerSummary, ItineraryPlan, ParsedTrip, TravelState
from app.tools import enrich, flights as flights_tool, places, stays as stays_tool, weather as weather_tool

logger = logging.getLogger(__name__)

ZERO_LLM_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "calls": []}


def _accumulate_usage(state: TravelState, node_name: str, provider: str, usage: dict) -> dict:
    """Folds one LLM call's usage into the run's running totals — same
    read-current/add/return-it pattern as the `llm_calls` counter, since
    LangGraph merges partial-state dicts rather than mutating in place."""
    totals = dict(state.get("llm_usage") or ZERO_LLM_USAGE)
    calls = [*totals.get("calls", []), {"node": node_name, "provider": provider, **usage}]
    return {
        "prompt_tokens": totals.get("prompt_tokens", 0) + usage["prompt_tokens"],
        "completion_tokens": totals.get("completion_tokens", 0) + usage["completion_tokens"],
        "total_tokens": totals.get("total_tokens", 0) + usage["total_tokens"],
        "cost_usd": round(totals.get("cost_usd", 0.0) + usage["cost_usd"], 6),
        "calls": calls,
    }


# Structured per-node logging: one JSON log line per node completion, with
# timing and a handful of small result-shape fields — enough to trace a run
# node-by-node in logs without dumping full flight/activity payloads.
_SUMMARY_FIELDS = (
    "flights",
    "stays",
    "activities",
    "weather",
    "itinerary",
    "route",
    "revision_count",
    "needs_clarification",
)


def _node_summary(result: dict) -> dict:
    summary: dict = {}
    for field in _SUMMARY_FIELDS:
        if field not in result:
            continue
        value = result[field]
        summary[f"{field}_count" if isinstance(value, list) else field] = len(value) if isinstance(value, list) else value
    if "critic_verdict" in result:
        verdict = result["critic_verdict"] or {}
        summary["critic_passed"] = verdict.get("passed")
        summary["critic_issues"] = len(verdict.get("issues", []))
    if "llm_usage" in result:
        summary["run_total_tokens"] = result["llm_usage"].get("total_tokens")
        summary["run_cost_usd"] = result["llm_usage"].get("cost_usd")
    return summary


def _logged_node(fn):
    @functools.wraps(fn)
    def wrapper(state: TravelState) -> dict:
        start = time.monotonic()
        result = fn(state)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        node_name = fn.__name__.removesuffix("_node")
        logger.info(json.dumps({"node": node_name, "duration_ms": duration_ms, **_node_summary(result)}, default=str))
        return result

    return wrapper

MAX_PARSE_ATTEMPTS = 2
MAX_REVISIONS = 2
HOTEL_NIGHT_ESTIMATE_USD = 120.0
ACTIVITY_DAY_ESTIMATE_USD = 30.0
FLIGHT_RETRY_OFFSETS_DAYS = (1, -1, 2, -2, 3, -3)

# Duffel test mode alone can return thousands of flight offers — passing all of
# them to the LLM blows past context/request-size limits (and burns tokens for
# nothing), so the planner only ever sees the cheapest few of each.
MAX_FLIGHTS_STORED = 20
MAX_FLIGHTS_FOR_PROMPT = 5
MAX_STAYS_FOR_PROMPT = 6
# A flat head-slice would starve later categories (the activities list is
# roughly grouped by category in fetch order) — cap per-category instead so
# the planner sees variety across all of them within the token budget.
MAX_ACTIVITIES_PER_CATEGORY_FOR_PROMPT = 3
MAX_ACTIVITIES_FOR_PROMPT = 30

ROUTE_BY_INTENT = {
    "full_trip": ["flight_agent", "stay_agent", "activities_agent"],
    "flights_only": ["flight_agent"],
    "stays_only": ["stay_agent"],
    "activities_only": ["activities_agent"],
}


def _shift_date(date_str: str | None, days: int) -> str | None:
    if not date_str:
        return None
    return (date.fromisoformat(date_str) + timedelta(days=days)).isoformat()


def _count_nights(start: str | None, end: str | None) -> int:
    if not start or not end:
        return 0
    return max((date.fromisoformat(end) - date.fromisoformat(start)).days, 0)


def _select_varied_activities(
    activities: list[dict],
    per_category: int = MAX_ACTIVITIES_PER_CATEGORY_FOR_PROMPT,
    max_total: int = MAX_ACTIVITIES_FOR_PROMPT,
) -> list[dict]:
    """Caps per-category (not just a head-slice) so every fetched category gets
    a fair shot at reaching the planner's prompt, then caps the overall total."""
    counts: dict[str, int] = {}
    selected = []
    for activity in activities:
        category = activity.get("type") or "web"
        if counts.get(category, 0) >= per_category:
            continue
        counts[category] = counts.get(category, 0) + 1
        selected.append(activity)
        if len(selected) >= max_total:
            break
    return selected


# Pre-summarized, lean copies of tool data for LLM prompts — the full objects
# (with segments, coordinates, ids) stay in state for the frontend/map/critic;
# the LLM only needs enough to choose and narrate, not render. This is what
# keeps the planner/finalizer prompts inside the free tier's token budget even
# with the richer multi-category activity set.


def _lean_flight(flight: dict) -> dict:
    return {
        "offer_id": flight.get("offer_id"),
        "carrier": flight.get("carrier"),
        "price": flight.get("price"),
        "currency": flight.get("currency"),
        "stops": flight.get("stops"),
        "duration": flight.get("duration"),
    }


def _lean_stay(stay: dict) -> dict:
    return {"hotel_id": stay.get("hotel_id"), "name": stay.get("name")}


def _lean_activity(activity: dict) -> dict:
    lean = {"name": activity.get("name"), "selectable": activity.get("selectable", False)}
    if activity.get("type"):
        lean["type"] = activity["type"]
    return lean


# ---- parser ----------------------------------------------------------------


def _build_memory_context(user_id: str, raw_query: str) -> str:
    prefs = memory.load_preferences(user_id)
    recalled = memory.recall_memory(user_id, raw_query)
    if not prefs and not recalled:
        return ""

    lines = []
    if prefs:
        lines.append(
            f"Stored preferences: budget_style={prefs.get('budget_style')}, pace={prefs.get('pace')}, "
            f"interests={prefs.get('interests')}, dietary={prefs.get('dietary')}"
        )
    lines.extend(f"From a previous trip: {chunk}" for chunk in recalled)

    return (
        "Known preferences for this RETURNING traveler — use them to fill gaps the current "
        "request leaves unstated, but anything explicit in the current request always wins:\n"
        + "\n".join(lines)
        + "\n\n"
    )


@_logged_node
def parser_node(state: TravelState) -> dict:
    raw_query = state["raw_query"]
    user_id = state.get("user_id")
    today = date.today().isoformat()
    llm_calls = state.get("llm_calls", 0)
    llm_usage = state.get("llm_usage") or ZERO_LLM_USAGE
    parsed_model = ParsedTrip()

    memory_context = _build_memory_context(user_id, raw_query) if user_id else ""

    for _ in range(MAX_PARSE_ATTEMPTS):
        user_prompt = f"Today's date: {today}\n\n{memory_context}Traveler request:\n{raw_query}"
        parsed_model, provider, usage = llm.generate_structured(prompts.PARSER_SYSTEM, user_prompt, ParsedTrip)
        llm_calls += 1
        llm_usage = _accumulate_usage({"llm_usage": llm_usage}, "parser", provider, usage)
        if not parsed_model.needs_clarification:
            break
        answer = interrupt({"question": parsed_model.clarify_question})
        raw_query = f"{raw_query}\n\nAdditional info from traveler: {answer}"

    return {
        "raw_query": raw_query,
        "parsed": parsed_model.model_dump(),
        "needs_clarification": parsed_model.needs_clarification,
        "clarify_question": parsed_model.clarify_question,
        "llm_calls": llm_calls,
        "llm_usage": llm_usage,
    }


# ---- supervisor --------------------------------------------------------------


@_logged_node
def supervisor_node(state: TravelState) -> dict:
    intent = state["parsed"].get("intent", "full_trip")
    return {"route": ROUTE_BY_INTENT.get(intent, ROUTE_BY_INTENT["full_trip"])}


# ---- agents -------------------------------------------------------------


@_logged_node
def flight_agent_node(state: TravelState) -> dict:
    parsed = state["parsed"]
    origin = parsed.get("origin")
    destinations = parsed.get("destinations") or []
    depart = parsed.get("start_date")
    if not origin or not destinations or not depart:
        return {"flights": []}

    destination = destinations[0]
    return_ = parsed.get("end_date")
    adults = parsed.get("travelers", 1)

    offers = flights_tool.search(origin, destination, depart, return_, adults)
    if not offers:
        for delta in FLIGHT_RETRY_OFFSETS_DAYS:
            offers = flights_tool.search(
                origin, destination, _shift_date(depart, delta), _shift_date(return_, delta), adults
            )
            if offers:
                break
    # Duffel test mode can return thousands of offers; keep the cheapest slice
    # so state/checkpoints stay small and the planner gets a sane candidate set.
    offers = sorted(offers, key=lambda o: o["price"])[:MAX_FLIGHTS_STORED]
    return {"flights": offers}


@_logged_node
def stay_agent_node(state: TravelState) -> dict:
    parsed = state["parsed"]
    destination_names = parsed.get("destination_names") or parsed.get("destinations") or []
    checkin = parsed.get("start_date")
    checkout = parsed.get("end_date")
    if not destination_names or not checkin or not checkout:
        return {"stays": []}
    adults = parsed.get("travelers", 1)
    return {"stays": stays_tool.search(destination_names[0], checkin, checkout, adults)}


@_logged_node
def activities_agent_node(state: TravelState) -> dict:
    parsed = state["parsed"]
    destination_names = parsed.get("destination_names") or parsed.get("destinations") or []
    if not destination_names:
        return {"activities": [], "weather": []}

    area = destination_names[0]
    # Always pull the rich baseline category mix (sights, viewpoints, museums, parks,
    # cafes, food, bars, markets, historic sites) on top of whatever the traveler
    # specifically mentioned, so the itinerary has real variety regardless of intent.
    interests = parsed.get("interests") or []
    categories = list(dict.fromkeys([*interests, *places.DEFAULT_ACTIVITY_CATEGORIES]))

    pois = [{**poi, "selectable": True} for poi in places.search(area, categories)]
    web_results = enrich.web(f"best things to do in {area}")
    activities = pois + [
        {"name": r["title"], "type": "web", "snippet": r["snippet"], "url": r["url"], "selectable": False}
        for r in web_results
        if r.get("title")
    ]

    weather_days: list[dict] = []
    start_date, end_date = parsed.get("start_date"), parsed.get("end_date")
    coords = places.geocode(area)
    if coords and start_date and end_date:
        lat, lon = coords
        weather_days = weather_tool.forecast(lat, lon, start_date, end_date)

    return {"activities": activities, "weather": weather_days}


# ---- planner -------------------------------------------------------------


def _compute_budget(plan: ItineraryPlan, flights: list[dict], parsed: dict) -> dict:
    flight_price = 0.0
    if plan.flight_offer_id:
        match = next((f for f in flights if f["offer_id"] == plan.flight_offer_id), None)
        flight_price = match["price"] if match else 0.0

    nights = _count_nights(parsed.get("start_date"), parsed.get("end_date"))
    stays_estimate = HOTEL_NIGHT_ESTIMATE_USD * nights if plan.hotel_id else 0.0
    activities_estimate = ACTIVITY_DAY_ESTIMATE_USD * len(plan.days)
    total = flight_price + stays_estimate + activities_estimate

    return {
        "flights": round(flight_price, 2),
        "stays_estimate": round(stays_estimate, 2),
        "activities_estimate": round(activities_estimate, 2),
        "total": round(total, 2),
        "currency": parsed.get("currency", "USD"),
        "note": "Flight price is real (Duffel test mode). Stay/activity costs are flat estimates, not quotes.",
    }


@_logged_node
def planner_node(state: TravelState) -> dict:
    parsed = state["parsed"]
    flights = state.get("flights", [])
    stays = state.get("stays", [])
    activities = state.get("activities", [])
    weather = state.get("weather", [])
    critic_verdict = state.get("critic_verdict")
    revision_count = state.get("revision_count", 0)

    is_revision = critic_verdict is not None and not critic_verdict.get("passed")
    if is_revision:
        revision_count += 1

    flights_for_prompt = sorted(flights, key=lambda f: f["price"])[:MAX_FLIGHTS_FOR_PROMPT]
    stays_for_prompt = stays[:MAX_STAYS_FOR_PROMPT]
    activities_for_prompt = _select_varied_activities(activities)

    context = {
        "trip": parsed,
        "flights": [_lean_flight(f) for f in flights_for_prompt],
        "stays": [_lean_stay(s) for s in stays_for_prompt],
        "activities": [_lean_activity(a) for a in activities_for_prompt],
        "weather": weather,
    }
    user_prompt = json.dumps(context, default=str, separators=(",", ":"))
    if is_revision:
        issues = "\n".join(f"- {issue}" for issue in critic_verdict.get("issues", []))
        user_prompt += f"\n\nCritic feedback from a previous attempt (you MUST fix these):\n{issues}"

    plan_model, provider, usage = llm.generate_structured(prompts.PLANNER_SYSTEM, user_prompt, ItineraryPlan)
    llm_calls = state.get("llm_calls", 0) + 1

    return {
        "itinerary": [d.model_dump() for d in plan_model.days],
        "selected_flight_offer_id": plan_model.flight_offer_id,
        "selected_hotel_id": plan_model.hotel_id,
        "budget_breakdown": _compute_budget(plan_model, flights, parsed),
        "revision_count": revision_count,
        "llm_calls": llm_calls,
        "llm_usage": _accumulate_usage(state, "planner", provider, usage),
    }


# ---- critic -------------------------------------------------------------


@_logged_node
def critic_node(state: TravelState) -> dict:
    parsed = state["parsed"]
    flights = state.get("flights", [])
    stays = state.get("stays", [])
    activities = state.get("activities", [])
    itinerary = state.get("itinerary", [])
    budget_breakdown = state.get("budget_breakdown", {})

    issues: list[str] = []

    flight_ids = {f["offer_id"] for f in flights}
    hotel_ids = {s["hotel_id"] for s in stays}
    selected_flight = state.get("selected_flight_offer_id")
    selected_hotel = state.get("selected_hotel_id")

    groundedness_ok = True
    if selected_flight and selected_flight not in flight_ids:
        groundedness_ok = False
        issues.append(f"Selected flight offer_id '{selected_flight}' is not in the retrieved flight data")
    if selected_hotel and selected_hotel not in hotel_ids:
        groundedness_ok = False
        issues.append(f"Selected hotel_id '{selected_hotel}' is not in the retrieved stay data")

    known_names = {a["name"] for a in activities if a.get("name") and a.get("selectable")}
    hotel_names = {s["name"] for s in stays if s.get("name")}
    seen_activity_names: dict[str, int] = {}
    variety_ok = True
    for day in itinerary:
        if day.get("suggested_hotel") and day["suggested_hotel"] not in hotel_names:
            groundedness_ok = False
            issues.append(
                f"Day {day.get('day_number')}'s suggested_hotel '{day['suggested_hotel']}' is not "
                "in the retrieved stay data"
            )
        for act in day.get("activities", []):
            if act["name"] not in known_names:
                groundedness_ok = False
                issues.append(
                    f"Activity '{act['name']}' on day {day.get('day_number')} is not in the "
                    "retrieved points-of-interest/web data"
                )
            seen_day = seen_activity_names.get(act["name"])
            if seen_day is not None and seen_day != day.get("day_number"):
                variety_ok = False
                issues.append(f"Activity '{act['name']}' repeats on days {seen_day} and {day.get('day_number')}")
            else:
                seen_activity_names[act["name"]] = day.get("day_number")

    budget = parsed.get("budget")
    budget_ok = True
    if budget is not None and budget_breakdown.get("total", 0) > budget:
        budget_ok = False
        issues.append(
            f"Estimated total {budget_breakdown.get('total')} {budget_breakdown.get('currency')} "
            f"exceeds the stated budget of {budget}"
        )

    day_balance_ok = all(len(day.get("activities", [])) > 0 for day in itinerary) if itinerary else True
    if not day_balance_ok:
        issues.append("One or more itinerary days have no activities")

    verdict = CriticVerdict(
        passed=groundedness_ok and budget_ok and day_balance_ok and variety_ok,
        groundedness_ok=groundedness_ok,
        budget_ok=budget_ok,
        day_balance_ok=day_balance_ok,
        variety_ok=variety_ok,
        issues=issues,
    )
    return {"critic_verdict": verdict.model_dump()}


def critic_router(state: TravelState) -> str:
    verdict = state.get("critic_verdict", {})
    if verdict.get("passed"):
        return "finalizer"
    if state.get("revision_count", 0) < MAX_REVISIONS:
        return "planner"
    return "finalizer"


# ---- finalizer -------------------------------------------------------------


def _budget_style(budget: float | None) -> str | None:
    if budget is None:
        return None
    if budget < 1000:
        return "shoestring"
    if budget < 3000:
        return "moderate"
    return "comfortable"


def _save_personalization(user_id: str, trip_id: str | None, parsed: dict) -> None:
    memory.save_preferences(
        user_id,
        budget_style=_budget_style(parsed.get("budget")),
        pace=parsed.get("pace"),
        interests=parsed.get("interests") or [],
        dietary=(parsed.get("constraints") or [None])[0],
    )
    destinations = parsed.get("destination_names") or parsed.get("destinations") or []
    summary = (
        f"Trip to {', '.join(destinations) or 'an unspecified destination'}: "
        f"interests={parsed.get('interests')}, pace={parsed.get('pace')}, "
        f"budget={parsed.get('budget')} {parsed.get('currency')}, travelers={parsed.get('travelers')}."
    )
    memory.write_memory(user_id, summary, source_trip_id=trip_id)


def _build_narrative_summary(state: TravelState) -> tuple[dict, int, dict]:
    """One grounded LLM call that narrates the already-validated structured plan
    — never re-derives facts, just writes up what's already in state. Returns
    (summary_dict, extra_llm_calls, llm_usage_delta)."""
    flights = state.get("flights", [])
    stays = state.get("stays", [])
    itinerary = state.get("itinerary", [])
    budget_breakdown = state.get("budget_breakdown", {})

    if not itinerary and not flights and not stays:
        return {}, 0, dict(ZERO_LLM_USAGE)

    selected_flight_id = state.get("selected_flight_offer_id")
    selected_hotel_id = state.get("selected_hotel_id")
    selected_flight = next((f for f in flights if f.get("offer_id") == selected_flight_id), None)
    selected_hotel = next((s for s in stays if s.get("hotel_id") == selected_hotel_id), None)

    context = {
        "trip": state.get("parsed"),
        "selected_flight": _lean_flight(selected_flight) if selected_flight else None,
        "selected_hotel": _lean_stay(selected_hotel) if selected_hotel else None,
        "itinerary": itinerary,
        "budget_breakdown": budget_breakdown,
    }
    user_prompt = json.dumps(context, default=str, separators=(",", ":"))
    try:
        summary_model, provider, usage = llm.generate_structured(prompts.FINALIZER_SYSTEM, user_prompt, FinalizerSummary)
        return summary_model.model_dump(), 1, {**usage, "provider": provider}
    except Exception as exc:
        logger.warning("finalizer narrative summary failed: %s", exc)
        return {}, 0, dict(ZERO_LLM_USAGE)


@_logged_node
def finalizer_node(state: TravelState) -> dict:
    narrative_summary, extra_llm_calls, narrative_usage = _build_narrative_summary(state)
    provider = narrative_usage.pop("provider", "none")
    llm_usage = (
        _accumulate_usage(state, "finalizer", provider, narrative_usage) if extra_llm_calls else state.get("llm_usage") or ZERO_LLM_USAGE
    )

    final = {
        "parsed": state.get("parsed"),
        "flights": state.get("flights", []),
        "stays": state.get("stays", []),
        "activities": state.get("activities", []),
        "weather": state.get("weather", []),
        "itinerary": state.get("itinerary", []),
        "selected_flight_offer_id": state.get("selected_flight_offer_id"),
        "selected_hotel_id": state.get("selected_hotel_id"),
        "budget_breakdown": state.get("budget_breakdown", {}),
        "critic_verdict": state.get("critic_verdict", {}),
        "narrative_summary": narrative_summary,
        "revision_count": state.get("revision_count", 0),
        "llm_calls": state.get("llm_calls", 0) + extra_llm_calls,
        "llm_usage": llm_usage,
    }

    user_id = state.get("user_id")
    if user_id:
        try:
            _save_personalization(user_id, state.get("trip_id"), state.get("parsed") or {})
        except Exception as exc:
            logger.warning("personalization save failed for user %s: %s", user_id, exc)

    return {"final": final, "llm_usage": llm_usage, "llm_calls": final["llm_calls"]}
