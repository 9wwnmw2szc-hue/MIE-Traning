from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.reply import BTN_MAIN_MENU, main_menu_keyboard
from app.services.quiz_service import QuizService
from app.utils import texts

logger = logging.getLogger(__name__)
router = Router(name="start")


async def _welcome(message: Message, session: AsyncSession, state: FSMContext) -> None:
    service = QuizService(session)
    user = message.from_user
    if user is None:
        await message.answer(texts.GENERIC_ERROR)
        return

    db_user, created = await service.ensure_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )
    if created:
        logger.info(
            "Зарегистрирован новый пользователь telegram_id=%s username=%s",
            user.id,
            user.username,
        )

    active = await service.get_active_attempt(db_user.id)
    await state.clear()
    await message.answer(
        texts.WELCOME_TEXT,
        reply_markup=main_menu_keyboard(has_active_attempt=active is not None),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _welcome(message, session, state)


@router.message(F.text == BTN_MAIN_MENU)
async def main_menu(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _welcome(message, session, state)
