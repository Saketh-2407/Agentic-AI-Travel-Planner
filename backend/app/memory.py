"""Supabase-backed persistence: profiles, preferences, trips, trip_results,
and pgvector memory_chunks for long-term personalization (Phase 3).

Uses the service-role key (server-side only, bypasses RLS) — the backend
itself enforces per-user scoping by always filtering on the JWT-verified
user_id (see app/auth.py). RLS in supabase/schema.sql is the defense-in-depth
backstop, not the primary mechanism, for this server-side path.
"""

import logging
from functools import lru_cache

from supabase import Client, create_client

from app import embeddings
from app.config import get_settings

logger = logging.getLogger(__name__)

MEMORY_RECALL_COUNT = 5


@lru_cache
def get_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def ensure_profile(user_id: str) -> None:
    client = get_client()
    existing = client.table("profiles").select("id").eq("id", user_id).execute()
    if not existing.data:
        client.table("profiles").insert({"id": user_id}).execute()


def load_preferences(user_id: str) -> dict | None:
    client = get_client()
    result = client.table("preferences").select("*").eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


def save_preferences(
    user_id: str,
    budget_style: str | None = None,
    pace: str | None = None,
    interests: list[str] | None = None,
    dietary: str | None = None,
) -> None:
    client = get_client()
    fields = {
        "user_id": user_id,
        "budget_style": budget_style,
        "pace": pace,
        "interests": interests or [],
        "dietary": dietary,
    }
    client.table("preferences").upsert(fields).execute()


def create_trip(user_id: str, raw_query: str, title: str | None = None) -> str:
    client = get_client()
    result = (
        client.table("trips")
        .insert({"user_id": user_id, "raw_query": raw_query, "title": title, "status": "pending"})
        .execute()
    )
    return result.data[0]["id"]


def get_trip(trip_id: str, user_id: str) -> dict | None:
    """Scoped to user_id — the backend's own ownership check, on top of RLS."""
    client = get_client()
    result = client.table("trips").select("*").eq("id", trip_id).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


def get_trip_by_share_id(share_id: str) -> dict | None:
    """No user scoping — `share_id` is the public, unguessable (uuid) key for
    the read-only /share page. See supabase/schema.sql's RLS note: this is
    deliberately a backend lookup by the opaque share_id, never a public
    'select * from trips' policy that would let anyone enumerate every trip."""
    client = get_client()
    result = client.table("trips").select("*").eq("share_id", share_id).execute()
    return result.data[0] if result.data else None


def update_trip(trip_id: str, **fields) -> None:
    client = get_client()
    client.table("trips").update(fields).eq("id", trip_id).execute()


def save_trip_results(trip_id: str, **fields) -> None:
    client = get_client()
    client.table("trip_results").upsert({"trip_id": trip_id, **fields}).execute()


def get_trip_results(trip_id: str) -> dict | None:
    client = get_client()
    result = client.table("trip_results").select("*").eq("trip_id", trip_id).execute()
    return result.data[0] if result.data else None


def list_trips(user_id: str) -> list[dict]:
    client = get_client()
    result = client.table("trips").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return result.data


def write_memory(user_id: str, content: str, source_trip_id: str | None = None) -> None:
    """Never raises — a memory write failure shouldn't break a trip's finalization."""
    try:
        vector = embeddings.embed(content)
        get_client().table("memory_chunks").insert(
            {"user_id": user_id, "content": content, "embedding": vector, "source_trip_id": source_trip_id}
        ).execute()
    except Exception as exc:
        logger.warning("write_memory failed for user %s: %s", user_id, exc)


def recall_memory(user_id: str, query_text: str, top_k: int = MEMORY_RECALL_COUNT) -> list[str]:
    """Never raises — returns [] on any failure so the parser degrades gracefully."""
    try:
        vector = embeddings.embed(query_text)
        result = get_client().rpc(
            "match_memory_chunks",
            {"query_embedding": vector, "match_user_id": user_id, "match_count": top_k},
        ).execute()
        return [row["content"] for row in result.data]
    except Exception as exc:
        logger.warning("recall_memory failed for user %s: %s", user_id, exc)
        return []
