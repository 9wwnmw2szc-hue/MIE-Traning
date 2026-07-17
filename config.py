from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    database_url: str
    questions_per_test: int = 20
    min_active_questions: int = 20


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///quiz_bot.db",
    ).strip()


def get_settings(*, require_token: bool = True) -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if require_token and not bot_token:
        raise RuntimeError(
            "BOT_TOKEN не задан. Создайте файл .env на основе .env.example "
            "и укажите токен бота от @BotFather."
        )

    return Settings(
        bot_token=bot_token,
        database_url=get_database_url(),
    )
