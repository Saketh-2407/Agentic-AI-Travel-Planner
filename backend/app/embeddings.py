"""Free text embeddings for long-term memory, via Gemini's embedding API.

This is a separate API + separate free quota from the chat model in app/llm.py,
so writing/reading memory never competes with parser/planner chat quota.
"""

import google.generativeai as genai

from app.config import get_settings

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768  # must match memory_chunks.embedding vector(768) in schema.sql

_configured = False


def embed(text: str) -> list[float]:
    global _configured
    if not _configured:
        genai.configure(api_key=get_settings().gemini_api_key)
        _configured = True
    result = genai.embed_content(model=EMBEDDING_MODEL, content=text, output_dimensionality=EMBEDDING_DIMENSIONS)
    return result["embedding"]
