"""
copilot.config — Application configuration loaded from environment variables.

WHAT: A single Settings object that holds all configurable values.
WHY:  We need API keys, model names, and feature flags to be configurable
      without changing code. Environment variables (via a .env file) are
      the standard way to do this in 12-factor apps.
HOW:  Pydantic Settings reads from environment variables automatically.
      Values in .env override defaults; real env vars override .env.

LEARN: pydantic-settings is a companion library to Pydantic that adds
"load from environment" capability. You define a class with typed fields,
and it automatically reads matching environment variables. This is much
safer than doing os.getenv("OPENAI_API_KEY") scattered throughout the code,
because: (1) all config is in one place, (2) types are validated at startup,
(3) you get clear errors if a required key is missing.

Usage:
    from copilot.config import settings
    print(settings.llm_provider)   # "openai" or "google"
    print(settings.openai_api_key) # The actual key (or None)
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# LEARN: We define the project root relative to this file's location.
# __file__ is the path to this config.py file. Going up 3 parents:
#   config.py → copilot/ → src/ → project_root/
# This gives us a reliable anchor for finding data/ and models/ directories.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class LLMProvider(str, Enum):
    """Supported LLM backends."""
    OPENAI = "openai"
    GOOGLE = "google"


class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables and .env file.

    LEARN: BaseSettings (from pydantic-settings) works just like a normal
    Pydantic BaseModel, but it ALSO reads values from environment variables.
    The field name is matched case-insensitively to env var names. So the
    field `openai_api_key` reads from the env var `OPENAI_API_KEY`.
    """

    # ── LLM configuration ────────────────────────────────────────────
    llm_provider: LLMProvider = Field(
        default=LLMProvider.OPENAI,
        description="Which LLM backend to use.",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key. Required if llm_provider is 'openai'.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model name.",
    )
    google_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key. Required if llm_provider is 'google'.",
    )
    google_model: str = Field(
        default="gemini-2.0-flash",
        description="Google model name.",
    )
    llm_temperature: float = Field(
        default=0.1,
        description="Temperature for LLM calls. Lower = more deterministic.",
        ge=0.0,
        le=2.0,
    )

    # ── Application settings ─────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Python logging level.")
    api_host: str = Field(default="0.0.0.0", description="FastAPI bind host.")
    api_port: int = Field(default=8000, description="FastAPI bind port.")

    # ── Paths ────────────────────────────────────────────────────────
    data_dir: Path = Field(
        default=PROJECT_ROOT / "data",
        description="Root directory for data files.",
    )
    models_dir: Path = Field(
        default=PROJECT_ROOT / "models",
        description="Root directory for trained ML model artifacts.",
    )

    # LEARN: model_config is a Pydantic Settings concept (not to be confused
    # with ML models!). It tells pydantic-settings WHERE to find the .env
    # file, what prefix to use for env vars, etc. `env_file = ".env"` means
    # it will look for a .env file in the current working directory.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Don't crash on unexpected env vars
    )


# LEARN: @lru_cache makes this function return the SAME Settings instance
# every time it's called (singleton pattern). This is important because:
# 1. We only read .env once (not on every import).
# 2. All modules share the same config object.
# 3. It's still testable — you can call get_settings.cache_clear() in tests.
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()


# Convenience alias for the common case
settings = get_settings()
