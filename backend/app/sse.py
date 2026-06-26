"""Maps LangGraph's per-node `stream(..., stream_mode="updates")` output to the
SSE event sequence from BUILD_PLAN.md section 10: parsed, clarify, agent_start/
agent_done, itinerary_partial, critic, final, error.
"""

import json
import logging
from typing import Any, Generator

from app import memory

logger = logging.getLogger(__name__)

AGENT_NODES = {"flight_agent", "stay_agent", "activities_agent"}


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _agent_summary(node_name: str, node_output: dict) -> str:
    if node_name == "flight_agent":
        return f"{len(node_output.get('flights', []))} flight offers found"
    if node_name == "stay_agent":
        return f"{len(node_output.get('stays', []))} stays found"
    if node_name == "activities_agent":
        n_activities = len(node_output.get("activities", []))
        n_weather = len(node_output.get("weather", []))
        return f"{n_activities} activities/places found, {n_weather} days of weather"
    return "done"


def stream_graph_events(graph, config: dict, graph_input: Any, trip_id: str) -> Generator[str, None, None]:
    """Runs (or resumes) the graph, yielding formatted SSE lines as each node
    completes. Persists the final result to Supabase before emitting `final`.
    Never raises out of the generator — failures become an `error` event so
    the SSE connection ends cleanly instead of a broken response."""
    revision_count = 0
    try:
        for update in graph.stream(graph_input, config, stream_mode="updates"):
            for node_name, node_output in update.items():
                if node_name == "__interrupt__":
                    # A node called interrupt() mid-execution (only the parser does this
                    # today) — no node-level update is emitted for it, just this marker.
                    question = node_output[0].value.get("question") if node_output else None
                    memory.update_trip(trip_id, status="needs_clarification")
                    yield _sse("clarify", {"question": question})

                elif node_name == "parser":
                    yield _sse("parsed", {"parsed": node_output.get("parsed")})

                elif node_name == "supervisor":
                    for agent in node_output.get("route", []):
                        yield _sse("agent_start", {"agent": agent})

                elif node_name in AGENT_NODES:
                    yield _sse("agent_done", {"agent": node_name, "summary": _agent_summary(node_name, node_output)})

                elif node_name == "planner":
                    revision_count = node_output.get("revision_count", revision_count)
                    yield _sse("itinerary_partial", {"itinerary": node_output.get("itinerary", [])})

                elif node_name == "critic":
                    yield _sse(
                        "critic", {"verdict": node_output.get("critic_verdict", {}), "revision": revision_count}
                    )

                elif node_name == "finalizer":
                    final = node_output.get("final", {})
                    _persist_final(trip_id, final)
                    yield _sse("final", final)
    except Exception as exc:
        logger.exception("graph stream failed for trip %s", trip_id)
        try:
            memory.update_trip(trip_id, status="error")
        except Exception:
            logger.exception("failed to mark trip %s as errored", trip_id)
        yield _sse("error", {"message": str(exc)})


def _persist_final(trip_id: str, final: dict) -> None:
    try:
        memory.update_trip(trip_id, status="done", parsed=final.get("parsed"))
        memory.save_trip_results(
            trip_id,
            flights=final.get("flights", []),
            stays=final.get("stays", []),
            activities=final.get("activities", []),
            itinerary=final.get("itinerary", []),
            budget=final.get("budget_breakdown"),
            narrative_summary=final.get("narrative_summary"),
            llm_calls=final.get("llm_calls", 0),
            llm_usage=final.get("llm_usage"),
            selected_flight_offer_id=final.get("selected_flight_offer_id"),
            selected_hotel_id=final.get("selected_hotel_id"),
        )
    except Exception:
        logger.exception("failed to persist final results for trip %s", trip_id)
