from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class BotSettings:
    bot_token: str
    api_base_url: str
    timeout_seconds: float = 20.0
    assessment_timeout_seconds: float = 70.0
    vacancy_timeout_seconds: float = 70.0


@lru_cache
def get_settings() -> BotSettings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    timeout_seconds = float(os.getenv("API_TIMEOUT_SECONDS", "20"))
    llm_timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    assessment_timeout_seconds = float(
        os.getenv(
            "ASSESSMENT_API_TIMEOUT_SECONDS",
            str(max(timeout_seconds, llm_timeout_seconds * 2 + 10)),
        )
    )
    vacancy_timeout_seconds = float(
        os.getenv(
            "VACANCY_API_TIMEOUT_SECONDS",
            str(max(timeout_seconds, llm_timeout_seconds * 2 + 10)),
        )
    )

    return BotSettings(
        bot_token=bot_token,
        api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8123").rstrip("/"),
        timeout_seconds=timeout_seconds,
        assessment_timeout_seconds=assessment_timeout_seconds,
        vacancy_timeout_seconds=vacancy_timeout_seconds,
    )
