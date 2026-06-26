import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

from app import memory
from app.auth import get_current_user_id
from app.config import get_settings
from app.graph.graph import build_graph
from app.graph.nodes import _accumulate_usage, _build_narrative_summary
from app.sse import stream_graph_events

# Without this, the root logger defaults to WARNING and every per-node
# structured log line in app.graph.nodes (logger.info(...)) is silently
# dropped — including in production, not just locally. INFO is the right
# default here: each line is one compact JSON object per node completion,
# not noisy per-request access logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

settings = get_settings()

app = FastAPI(title="Wayfare API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def _get_owned_trip(trip_id: str, user_id: str) -> dict:
    trip = memory.get_trip(trip_id, user_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class CreateTripRequest(BaseModel):
    query: str


@app.post("/trips")
def create_trip(body: CreateTripRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    """Just creates the trip record — running the graph happens when the
    client opens the SSE stream below, so progress is visible live rather
    than the client blocking on one big synchronous call."""
    memory.ensure_profile(user_id)
    trip_id = memory.create_trip(user_id, body.query, title=body.query[:80])
    return {"trip_id": trip_id, "thread_id": trip_id}


@app.get("/trips/{trip_id}/stream")
def stream_trip(trip_id: str, user_id: str = Depends(get_current_user_id)) -> StreamingResponse:
    trip = _get_owned_trip(trip_id, user_id)
    config = {"configurable": {"thread_id": trip_id}}
    graph_input = {
        "raw_query": trip["raw_query"],
        "user_id": user_id,
        "trip_id": trip_id,
        "llm_calls": 0,
        "revision_count": 0,
    }
    return StreamingResponse(
        stream_graph_events(_get_graph(), config, graph_input, trip_id), media_type="text/event-stream"
    )


class AnswerRequest(BaseModel):
    answer: str


@app.post("/trips/{trip_id}/answer")
def answer_trip(trip_id: str, body: AnswerRequest, user_id: str = Depends(get_current_user_id)) -> StreamingResponse:
    """Resumes a graph paused on a `clarify` interrupt with the user's reply,
    streaming the rest of the run (agent_start/agent_done...final) the same
    way the initial /stream call does."""
    _get_owned_trip(trip_id, user_id)
    config = {"configurable": {"thread_id": trip_id}}
    return StreamingResponse(
        stream_graph_events(_get_graph(), config, Command(resume=body.answer), trip_id),
        media_type="text/event-stream",
    )


@app.get("/trips")
def get_trips(user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return memory.list_trips(user_id)


@app.get("/trips/{trip_id}")
def get_trip_detail(trip_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    trip = _get_owned_trip(trip_id, user_id)
    return {**trip, "results": memory.get_trip_results(trip_id)}


@app.get("/share/{share_id}")
def get_shared_trip(share_id: str) -> dict:
    """Public, read-only — no auth. Looked up by the opaque share_id (not the
    trip's primary id), so a link only exposes the one trip it was generated
    for. See supabase/schema.sql's RLS note for why this is a backend lookup
    rather than a public table policy."""
    trip = memory.get_trip_by_share_id(share_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Shared trip not found")
    return {**trip, "results": memory.get_trip_results(trip["id"])}


@app.post("/trips/{trip_id}/regenerate-summary")
def regenerate_summary(trip_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    """Retries only the finalizer's narrative-summary call — for a trip whose
    summary came back blank because quota ran out mid-run. Reuses the already-
    validated structured plan (itinerary, selected flight/hotel, budget) from
    trip_results; never re-runs the planner/critic, so it can't change the
    underlying plan, only narrate it."""
    trip = _get_owned_trip(trip_id, user_id)
    results = memory.get_trip_results(trip_id)
    if results is None:
        raise HTTPException(status_code=404, detail="This trip has no saved results yet")

    state = {
        "parsed": trip.get("parsed"),
        "flights": results.get("flights", []),
        "stays": results.get("stays", []),
        "itinerary": results.get("itinerary", []),
        "budget_breakdown": results.get("budget"),
        "selected_flight_offer_id": results.get("selected_flight_offer_id"),
        "selected_hotel_id": results.get("selected_hotel_id"),
        "llm_usage": results.get("llm_usage"),
    }
    narrative_summary, extra_llm_calls, usage = _build_narrative_summary(state)
    if not narrative_summary:
        raise HTTPException(status_code=502, detail="Regenerating the summary failed — please try again shortly")

    provider = usage.pop("provider", "none")
    updated_usage = (
        _accumulate_usage(state, "finalizer", provider, usage) if extra_llm_calls else (state.get("llm_usage") or {})
    )
    memory.save_trip_results(
        trip_id,
        narrative_summary=narrative_summary,
        llm_calls=results.get("llm_calls", 0) + extra_llm_calls,
        llm_usage=updated_usage,
    )
    return {"narrative_summary": narrative_summary}
