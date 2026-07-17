from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.reply import BTN_MY_RESULTS, main_menu_keyboard
from app.services.quiz_service import QuizService
from app.services.result_service import ResultService
from app.utils import texts

router = Router(name="results")


@router.message(F.text == BTN_MY_RESULTS)
async def my_results(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        await message.answer(texts.GENERIC_ERROR)
        return

    quiz_service = QuizService(session)
    db_user, _ = await quiz_service.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    result_service = ResultService(session)
    stats = await result_service.get_user_stats(db_user.id)
    active = await quiz_service.get_active_attempt(db_user.id)

    if stats is None:
        await message.answer(
            texts.NO_RESULTS,
            reply_markup=main_menu_keyboard(has_active_attempt=active is not None),
        )
        return

    await message.answer(
        ResultService.format_stats(stats),
        reply_markup=main_menu_keyboard(has_active_attempt=active is not None),
    )
