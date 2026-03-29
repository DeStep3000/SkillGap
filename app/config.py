from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    llm_provider: str | None
    llm_timeout_seconds: float
    openrouter_api_key: str | None
    openrouter_base_url: str
    openrouter_app_name: str
    openrouter_site_url: str | None
    openrouter_extraction_model: str | None
    openrouter_explanation_model: str | None
    openrouter_vacancy_model: str | None
    api_title: str = "SkillGap API"
    api_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://skillgap:skillgap@127.0.0.1:5432/skillgap",
        ),
        data_dir=BASE_DIR / "app" / "data",
        llm_provider=os.getenv("LLM_PROVIDER", "").strip() or None,
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip() or None,
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        ).rstrip("/"),
        openrouter_app_name=os.getenv("OPENROUTER_APP_NAME", "SkillGap"),
        openrouter_site_url=os.getenv("OPENROUTER_SITE_URL", "").strip() or None,
        openrouter_extraction_model=os.getenv("OPENROUTER_EXTRACTION_MODEL", "").strip()
        or None,
        openrouter_explanation_model=os.getenv(
            "OPENROUTER_EXPLANATION_MODEL", ""
        ).strip()
        or None,
        openrouter_vacancy_model=os.getenv("OPENROUTER_VACANCY_MODEL", "").strip()
        or None,
    )
