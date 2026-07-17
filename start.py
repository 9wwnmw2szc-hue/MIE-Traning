#!/usr/bin/env python3
"""Railway / production entrypoint: import questions, then start the bot."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.services.import_service import run_import
from app.utils.logging import setup_logging
from config import get_database_url, get_settings

ROOT = Path(__file__).resolve().parent
QUESTIONS = ROOT / "data" / "questions.json"


async def prepare_database() -> None:
    logger = logging.getLogger("startup")
    database_url = get_database_url()
    imported, skipped, errors = await run_import(database_url, QUESTIONS)
    logger.info(
        "Импорт вопросов: загружено=%s пропущено=%s ошибок=%s",
        imported,
        skipped,
        len(errors),
    )
    for error in errors[:10]:
        logger.error("Ошибка импорта: %s", error)


async def run() -> None:
    setup_logging()
    get_settings(require_token=True)
    await prepare_database()

    from bot import main as bot_main

    await bot_main()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
