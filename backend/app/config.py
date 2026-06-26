import re
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    llm_dev_cache: bool = False
    duffel_api_key: str = ""
    duffel_base_url: str = "https://api.duffel.com"
    tavily_api_key: str = ""
    osm_contact_email: str = "darpallysaketh@gmail.com"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_db_url: str = ""  # direct Postgres connection string, for the LangGraph checkpointer
    allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Exact-match origins only — entries containing `*` (e.g. a temporary
        `https://*.vercel.app` wildcard) belong in `allowed_origin_regex`
        instead, since Starlette's CORSMiddleware does literal string
        comparison here, not glob matching."""
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip() and "*" not in origin
        ]

    @property
    def allowed_origin_regex(self) -> str | None:
        """Combines every `*`-containing entry in ALLOWED_ORIGINS into one
        regex for CORSMiddleware's `allow_origin_regex` — the actual
        mechanism Starlette supports for wildcard origins."""
        patterns = [origin.strip() for origin in self.allowed_origins.split(",") if "*" in origin]
        if not patterns:
            return None
        regexes = [re.escape(p).replace(r"\*", ".*") for p in patterns]
        return "^(" + "|".join(regexes) + ")$"


@lru_cache
def get_settings() -> Settings:
    return Settings()
