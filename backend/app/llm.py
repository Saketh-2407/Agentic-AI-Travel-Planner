"""Structured-output LLM calls: Gemini 2.5 Flash primary, then Groq (Llama
3.3 70B), then OpenRouter's free models, each tried in turn on a rate limit
or other failure. All paths return a validated instance of the given
Pydantic schema, so callers don't care which provider answered.
"""

import json
import logging
import re
import time
from typing import TypeVar

import google.generativeai as genai
import httpx
from groq import Groq
from pydantic import BaseModel, ValidationError

from app import llm_cache
from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_gemini_configured = False
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
RETRIES_PER_PROVIDER = 2
RETRY_BACKOFF_SECONDS = 2

# Notional USD-per-1M-token rates, for the observability/eval cost story only —
# every provider here is used on its free tier, so actual billing is $0. This
# answers "what would this run have cost on a paid plan", not a real invoice.
_RATES_PER_1M_TOKENS = {
    "gemini": {"prompt": 0.30, "completion": 2.50},
    "groq": {"prompt": 0.59, "completion": 0.79},
    "openrouter": {"prompt": 0.0, "completion": 0.0},  # ":free" model variant
}

ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}


def _usage(provider: str, prompt_tokens: int, completion_tokens: int) -> dict:
    rates = _RATES_PER_1M_TOKENS.get(provider, {"prompt": 0.0, "completion": 0.0})
    cost = (prompt_tokens * rates["prompt"] + completion_tokens * rates["completion"]) / 1_000_000
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(cost, 6),
    }


def _add_usage(a: dict, b: dict) -> dict:
    return {
        "prompt_tokens": a["prompt_tokens"] + b["prompt_tokens"],
        "completion_tokens": a["completion_tokens"] + b["completion_tokens"],
        "total_tokens": a["total_tokens"] + b["total_tokens"],
        "cost_usd": round(a["cost_usd"] + b["cost_usd"], 6),
    }


def _strip_code_fence(text: str) -> str:
    """Models occasionally wrap JSON in ```json ... ``` despite instructions not to."""
    match = _CODE_FENCE_RE.match(text.strip())
    return match.group(1) if match else text


def _parse(raw: str, schema: type[T]) -> T:
    return schema.model_validate_json(_strip_code_fence(raw))


def _gemini_raw(schema: type[T], system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    global _gemini_configured
    settings = get_settings()
    if not _gemini_configured:
        genai.configure(api_key=settings.gemini_api_key)
        _gemini_configured = True

    # Passing `schema` directly as response_schema hits a bug in this SDK version
    # ("Unknown field for Schema: default") for any Pydantic model with default
    # values. Prompt-embedding the JSON schema + response_mime_type="application/json"
    # is robust across schema shapes and matches the Groq/OpenRouter paths below.
    schema_hint = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    full_system = f"{system_prompt}\n\nRespond with ONLY valid JSON matching this schema:\n{schema_hint}"

    model = genai.GenerativeModel(settings.gemini_model, system_instruction=full_system)
    response = model.generate_content(
        user_prompt,
        generation_config=genai.GenerationConfig(response_mime_type="application/json", temperature=0.1),
    )
    usage_meta = getattr(response, "usage_metadata", None)
    prompt_tokens = getattr(usage_meta, "prompt_token_count", 0) or 0
    completion_tokens = getattr(usage_meta, "candidates_token_count", 0) or 0
    return response.text, _usage("gemini", prompt_tokens, completion_tokens)


def _groq_raw(schema: type[T], system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)
    schema_hint = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": f"{system_prompt}\n\nRespond with JSON matching this schema:\n{schema_hint}",
            },
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    return response.choices[0].message.content, _usage("groq", prompt_tokens, completion_tokens)


def _openrouter_raw(schema: type[T], system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    """Third fallback (BUILD_PLAN section 15): OpenRouter's free models, for
    extra daily headroom once Gemini and Groq are both exhausted. Free models
    vary in how reliably they honor response_format, so — like Groq — we lean
    on the prompt-embedded schema rather than a strict json mode."""
    settings = get_settings()
    schema_hint = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}", "Content-Type": "application/json"},
        json={
            "model": settings.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": f"{system_prompt}\n\nRespond with ONLY valid JSON matching this schema:\n{schema_hint}",
                },
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    body = response.json()
    usage = body.get("usage", {})
    return (
        body["choices"][0]["message"]["content"],
        _usage("openrouter", usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
    )


def _call_with_repair(raw_fn, schema: type[T], system_prompt: str, user_prompt: str) -> tuple[T, dict]:
    """Calls `raw_fn` for raw text, parses it, and — if parsing fails — makes
    ONE repair attempt asking the same provider to fix its own invalid output,
    rather than immediately falling back to the next provider. Returns the
    combined usage across both calls if a repair was needed."""
    raw, usage = raw_fn(schema, system_prompt, user_prompt)
    try:
        return _parse(raw, schema), usage
    except (ValueError, ValidationError) as exc:
        logger.warning("Response failed schema validation (%s) — asking provider to repair it", exc)
        repair_prompt = (
            f"{user_prompt}\n\nYour previous response was not valid JSON for the required schema "
            f"(error: {exc}). Previous response:\n{raw}\n\n"
            "Return ONLY the corrected, valid JSON — no markdown fences, no commentary."
        )
        repaired_raw, repair_usage = raw_fn(schema, system_prompt, repair_prompt)
        return _parse(repaired_raw, schema), _add_usage(usage, repair_usage)


PROVIDERS: list[tuple[str, object]] = [
    ("gemini", _gemini_raw),
    ("groq", _groq_raw),
    ("openrouter", _openrouter_raw),
]


def generate_structured(system_prompt: str, user_prompt: str, schema: type[T]) -> tuple[T, str, dict]:
    """Returns (parsed_result, provider_used, usage) — provider is "gemini",
    "groq", "openrouter", "cache", or "cache-synthetic" (see llm_cache's
    cache-integrity note: a synthetic entry is a hand-written stand-in, never
    real model output). `usage` is {prompt_tokens, completion_tokens,
    total_tokens, cost_usd} — all zero for cache hits, since no real call was made.

    Tries each provider in turn, retrying each a couple of times before moving
    on — all three run on free tiers, where a transient 429 is the common case,
    not the exception. Raises only once every provider is exhausted.

    If LLM_DEV_CACHE is on, an exact (system_prompt, user_prompt, schema) match
    is replayed from disk instead of calling any provider at all."""
    settings = get_settings()
    if settings.llm_dev_cache:
        cached = llm_cache.get(system_prompt, user_prompt, schema.__name__)
        if cached is not None:
            raw, is_synthetic = cached
            if is_synthetic:
                logger.warning("Replaying a SYNTHETIC (hand-written, non-real) cache entry — not real model output")
            return _parse(raw, schema), ("cache-synthetic" if is_synthetic else "cache"), dict(ZERO_USAGE)

    result, provider, usage = _generate_live(system_prompt, user_prompt, schema)

    if settings.llm_dev_cache:
        llm_cache.put(system_prompt, user_prompt, schema.__name__, result.model_dump_json(), synthetic=False)

    return result, provider, usage


def _generate_live(system_prompt: str, user_prompt: str, schema: type[T]) -> tuple[T, str, dict]:
    last_exc: Exception | None = None
    for name, raw_fn in PROVIDERS:
        for attempt in range(RETRIES_PER_PROVIDER):
            try:
                result, usage = _call_with_repair(raw_fn, schema, system_prompt, user_prompt)
                return result, name, usage
            except Exception as exc:
                last_exc = exc
                logger.warning("%s call failed (attempt %d/%d): %s", name, attempt + 1, RETRIES_PER_PROVIDER, exc)
                if attempt < RETRIES_PER_PROVIDER - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS)
        logger.warning("%s exhausted retries — trying next provider", name)
    raise RuntimeError("All LLM providers failed (Gemini, Groq, OpenRouter all exhausted)") from last_exc
