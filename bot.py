from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from app.database.database import close_db, init_db
from app.handlers import setup_routers
from app.middlewares.db import DbSessionMiddleware
from app.utils.logging import setup_logging
from config import get_settings

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_settings()

    await init_db()
    logger.info("База данных инициализирована")

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(DbSessionMiddleware())
    dispatcher.include_router(setup_routers())

    @dispatcher.error()
    async def on_error(event: ErrorEvent) -> bool:
        logger.exception(
            "Необработанное исключение update_id=%s",
            getattr(event.update, "update_id", None),
            exc_info=event.exception,
        )
        return True

    logger.info("Бот запускается")
    try:
        await dispatcher.start_polling(bot)
    finally:
        logger.info("Бот останавливается")
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Бот остановлен")
