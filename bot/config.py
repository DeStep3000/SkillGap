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


@lru_cache
def get_settings() -> BotSettings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    return BotSettings(
        bot_token=bot_token,
        api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        timeout_seconds=float(os.getenv("API_TIMEOUT_SECONDS", "20")),
    )

