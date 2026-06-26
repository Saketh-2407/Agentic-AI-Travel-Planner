"""Builds and compiles the LangGraph travel-planning graph.

Checkpointer: the Supabase Postgres checkpointer when SUPABASE_DB_URL is
configured (Phase 3+); falls back to local SQLite otherwise, so the graph
still runs without a Supabase project (e.g. quick local iteration, CI).
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.graph import nodes
from app.graph.state import TravelState

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent.parent.parent / ".cache" / "checkpoints.sqlite"

_postgres_pool = None  # kept open for the process lifetime; reused across build_graph() calls


def _supervisor_route(state: TravelState) -> list[str]:
    return state.get("route", [])


def _build_checkpointer(sqlite_path: Path | str):
    settings = get_settings()
    if settings.supabase_db_url:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool

        global _postgres_pool
        if _postgres_pool is None:
            _postgres_pool = ConnectionPool(
                conninfo=settings.supabase_db_url,
                max_size=5,
                kwargs={"autocommit": True, "prepare_threshold": 0},
            )
        checkpointer = PostgresSaver(_postgres_pool)
        checkpointer.setup()  # idempotent: creates checkpoint tables on first run
        return checkpointer

    sqlite_path = Path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(sqlite_path), check_same_thread=False)
    return SqliteSaver(conn)


def build_graph(sqlite_path: Path | str = DEFAULT_SQLITE_PATH):
    checkpointer = _build_checkpointer(sqlite_path)

    builder = StateGraph(TravelState)
    builder.add_node("parser", nodes.parser_node)
    builder.add_node("supervisor", nodes.supervisor_node)
    builder.add_node("flight_agent", nodes.flight_agent_node)
    builder.add_node("stay_agent", nodes.stay_agent_node)
    builder.add_node("activities_agent", nodes.activities_agent_node)
    builder.add_node("planner", nodes.planner_node)
    builder.add_node("critic", nodes.critic_node)
    builder.add_node("finalizer", nodes.finalizer_node)

    builder.add_edge(START, "parser")
    builder.add_edge("parser", "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        _supervisor_route,
        {
            "flight_agent": "flight_agent",
            "stay_agent": "stay_agent",
            "activities_agent": "activities_agent",
        },
    )
    builder.add_edge("flight_agent", "planner")
    builder.add_edge("stay_agent", "planner")
    builder.add_edge("activities_agent", "planner")
    builder.add_edge("planner", "critic")
    builder.add_conditional_edges(
        "critic",
        nodes.critic_router,
        {"planner": "planner", "finalizer": "finalizer"},
    )
    builder.add_edge("finalizer", END)

    return builder.compile(checkpointer=checkpointer)
