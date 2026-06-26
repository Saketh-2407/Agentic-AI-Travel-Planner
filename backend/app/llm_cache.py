"""Dev-only LLM response cache/replay — separate from app/tools/cache.py's
tool_cache. Lets fixed test scenarios (run_cli.py, the Phase 6 eval harness)
re-run without re-spending the daily Gemini/Groq/OpenRouter quota. Enabled by
setting LLM_DEV_CACHE=true in .env; never consulted unless that flag is on,
so it has no effect on real production traffic.

Cache integrity (BUILD_PLAN section 15): every entry is tagged `synthetic`.
Real entries (synthetic=False) are recordings of an actual model response.
Synthetic entries (synthetic=True) are hand-written stand-ins written when
quota was exhausted — never real model output. Synthetic entries must be
replaced with a real recording once quota allows, and must never be treated
as ground truth by the Phase 6 eval harness.
"""

import hashlib
import json
from pathlib import Path

_CACHE_FILE = Path(__file__).resolve().parent.parent / ".cache" / "llm_dev_cache.json"


def _key(system_prompt: str, user_prompt: str, schema_name: str) -> str:
    payload = json.dumps({"system": system_prompt, "user": user_prompt, "schema": schema_name}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _load() -> dict[str, dict]:
    if not _CACHE_FILE.exists():
        return {}
    try:
        return json.loads(_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, dict]) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(data, indent=2))


def get(system_prompt: str, user_prompt: str, schema_name: str) -> tuple[str, bool] | None:
    """Returns (raw_json, is_synthetic), or None if not cached."""
    entry = _load().get(_key(system_prompt, user_prompt, schema_name))
    if entry is None:
        return None
    if isinstance(entry, str):  # entries written before the synthetic flag existed
        return entry, False
    return entry["raw"], entry.get("synthetic", False)


def put(system_prompt: str, user_prompt: str, schema_name: str, raw_json: str, synthetic: bool = False) -> None:
    data = _load()
    data[_key(system_prompt, user_prompt, schema_name)] = {"raw": raw_json, "synthetic": synthetic}
    _save(data)


def list_synthetic_keys() -> list[str]:
    """Cache keys still backed by a hand-written stand-in, not a real model
    response — use this to confirm none remain before trusting the cache
    for the Phase 6 eval harness."""
    return [key for key, entry in _load().items() if isinstance(entry, dict) and entry.get("synthetic")]
