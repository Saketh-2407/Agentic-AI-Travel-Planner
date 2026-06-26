"""Argument-hash cache shared by every tool.

Two tiers: an in-memory dict (fast, per-process) and a JSON file on disk
(survives across separate script runs / process restarts). Same shape as the
`tool_cache` Supabase table from the build plan (key, value, expires_at), so
swapping the disk tier for a real Supabase table in Phase 3 is a drop-in change.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

_MEMORY_CACHE: dict[str, tuple[float, Any]] = {}

_CACHE_FILE = Path(__file__).resolve().parent.parent.parent / ".cache" / "tool_cache.json"


def _make_key(namespace: str, params: dict[str, Any]) -> str:
    payload = json.dumps({"namespace": namespace, "params": params}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_disk_cache() -> dict[str, dict[str, Any]]:
    if not _CACHE_FILE.exists():
        return {}
    try:
        return json.loads(_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_disk_cache(data: dict[str, dict[str, Any]]) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(data))


def get_or_set(namespace: str, params: dict[str, Any], ttl_seconds: int, compute: Callable[[], Any]) -> Any:
    """Return the cached value for (namespace, params) if fresh, else call
    `compute()`, cache the result, and return it."""
    key = _make_key(namespace, params)
    now = time.time()

    hit = _MEMORY_CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]

    disk = _load_disk_cache()
    entry = disk.get(key)
    if entry and entry["expires_at"] > now:
        _MEMORY_CACHE[key] = (entry["expires_at"], entry["value"])
        return entry["value"]

    value = compute()
    expires_at = now + ttl_seconds
    _MEMORY_CACHE[key] = (expires_at, value)
    disk[key] = {"expires_at": expires_at, "value": value}
    _save_disk_cache(disk)
    return value
