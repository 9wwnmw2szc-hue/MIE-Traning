from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.inline import answers_keyboard
from app.keyboards.reply import (
    BTN_CANCEL,
    BTN_CONTINUE,
    BTN_CONTINUE_TEST,
    BTN_RESTART,
    BTN_RETRY,
    BTN_SHOW_ERRORS,
    BTN_START_TEST,
    active_test_conflict_keyboard,
    finish_menu_keyboard,
    main_menu_keyboard,
)
from app.services.quiz_service import QuestionPayload, QuizService
from app.services.result_service import ResultService
from app.states.quiz import QuizStates
from app.utils import texts

logger = logging.getLogger(__name__)
router = Router(name="quiz")


def _format_question(payload: QuestionPayload) -> str:
    lines = [
        f"Вопрос {payload.position} из {payload.total}",
        "",
        payload.text,
        "",
    ]
    lines.extend(payload.option_labels)
    return "\n".join(lines)


async def _send_question(message: Message, payload: QuestionPayload) -> None:
    await message.answer(
        _format_question(payload),
        reply_markup=answers_keyboard(
            attempt_id=payload.attempt_id,
            question_id=payload.question_id,
            options=payload.options,
        ),
    )


async def _begin_attempt(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    *,
    restart: bool = False,
) -> None:
    service = QuizService(session)
    user = message.from_user
    if user is None:
        await message.answer(texts.GENERIC_ERROR)
        return

    db_user, _ = await service.ensure_user(user.id, user.username, user.full_name)

    try:
        if restart:
            attempt = await service.restart_test(db_user)
        else:
            attempt = await service.start_test(db_user)
    except RuntimeError as exc:
        if str(exc) == "not_enough_questions":
            await message.answer(texts.NOT_ENOUGH_QUESTIONS)
            return
        if str(exc) == "active_attempt_exists":
            await state.set_state(QuizStates.conflict)
            await message.answer(
                texts.ACTIVE_TEST_EXISTS,
                reply_markup=active_test_conflict_keyboard(),
            )
            return
        logger.exception("Не удалось начать тест")
        await message.answer(texts.GENERIC_ERROR)
        return
    except Exception:
        logger.exception("Ошибка базы данных при старте теста")
        await message.answer(texts.GENERIC_ERROR)
        return

    question = await service.get_current_question(attempt)
    if question is None:
        await message.answer(texts.GENERIC_ERROR)
        return

    await state.set_state(QuizStates.answering)
    await state.update_data(attempt_id=attempt.id)
    await message.answer(texts.TEST_STARTED_TEXT)
    await _send_question(message, question)


async def _continue_attempt(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    service = QuizService(session)
    user = message.from_user
    if user is None:
        await message.answer(texts.GENERIC_ERROR)
        return

    db_user, _ = await service.ensure_user(user.id, user.username, user.full_name)
    attempt = await service.get_active_attempt(db_user.id)
    if attempt is None:
        await message.answer(
            "Нет незавершённого теста.",
            reply_markup=main_menu_keyboard(has_active_attempt=False),
        )
        await state.clear()
        return

    question = await service.get_current_question(attempt)
    if question is None:
        await message.answer(texts.GENERIC_ERROR)
        return

    await state.set_state(QuizStates.answering)
    await state.update_data(attempt_id=attempt.id)
    await message.answer("Продолжаем тест.")
    await _send_question(message, question)


@router.message(F.text == BTN_START_TEST)
async def start_test(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _begin_attempt(message, session, state, restart=False)


@router.message(F.text == BTN_RETRY)
async def retry_test(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _begin_attempt(message, session, state, restart=True)


@router.message(F.text.in_({BTN_CONTINUE_TEST, BTN_CONTINUE}))
async def continue_test(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _continue_attempt(message, session, state)


@router.message(F.text == BTN_RESTART)
async def restart_test(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _begin_attempt(message, session, state, restart=True)


@router.message(F.text == BTN_CANCEL)
async def cancel_conflict(message: Message, session: AsyncSession, state: FSMContext) -> None:
    service = QuizService(session)
    user = message.from_user
    has_active = False
    if user is not None:
        db_user, _ = await service.ensure_user(user.id, user.username, user.full_name)
        has_active = await service.get_active_attempt(db_user.id) is not None
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=main_menu_keyboard(has_active_attempt=has_active),
    )


@router.callback_query(F.data.startswith("a:"))
async def process_answer(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if callback.message is None or callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer(texts.STALE_ANSWER, show_alert=True)
        return

    try:
        attempt_id = int(parts[1])
        question_id = int(parts[2])
        option_id = int(parts[3])
    except ValueError:
        await callback.answer(texts.STALE_ANSWER, show_alert=True)
        return

    service = QuizService(session)
    try:
        status, attempt, next_question = await service.submit_answer(
            attempt_id=attempt_id,
            question_id=question_id,
            option_id=option_id,
        )
    except Exception:
        logger.exception("Ошибка при сохранении ответа")
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    if status == "already_answered":
        await callback.answer(texts.ALREADY_ANSWERED, show_alert=False)
        return

    if status in {"stale", "not_found", "missing_question"}:
        await callback.answer(texts.STALE_ANSWER, show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.debug("Не удалось убрать клавиатуру у сообщения", exc_info=True)

    await callback.answer()

    if status == "completed" and attempt is not None:
        await state.set_state(QuizStates.finished)
        await state.update_data(attempt_id=attempt.id)
        finish_text = ResultService.format_finish_message(attempt)
        await callback.message.answer(
            finish_text,
            reply_markup=finish_menu_keyboard(),
        )
        return

    if next_question is not None:
        await state.set_state(QuizStates.answering)
        await state.update_data(attempt_id=next_question.attempt_id)
        await callback.message.answer(
            _format_question(next_question),
            reply_markup=answers_keyboard(
                attempt_id=next_question.attempt_id,
                question_id=next_question.question_id,
                options=next_question.options,
            ),
        )


@router.message(F.text == BTN_SHOW_ERRORS)
async def show_errors(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    attempt_id = data.get("attempt_id")
    service = QuizService(session)

    if attempt_id is None:
        user = message.from_user
        if user is None:
            await message.answer(texts.GENERIC_ERROR)
            return
        db_user, _ = await service.ensure_user(user.id, user.username, user.full_name)
        from app.database.repositories import AttemptRepository

        completed = await AttemptRepository(session).get_completed_for_user(db_user.id)
        if not completed:
            await message.answer(texts.NO_RESULTS)
            return
        attempt_id = completed[0].id

    wrong_answers = await service.get_wrong_answers(int(attempt_id))
    if not wrong_answers:
        await message.answer(texts.NO_ERRORS)
        return

    for answer in wrong_answers:
        correct_option = next(
            (opt for opt in answer.question.options if opt.is_correct),
            None,
        )
        correct_text = correct_option.option_text if correct_option else "—"
        selected_text = answer.selected_option.option_text if answer.selected_option else "—"
        text = (
            "Вопрос:\n"
            f"{answer.question.question_text}\n\n"
            f"Ваш ответ: {selected_text}\n"
            f"Правильный ответ: {correct_text}"
        )
        await message.answer(text)
