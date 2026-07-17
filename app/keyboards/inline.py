from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def answers_keyboard(
    attempt_id: int,
    question_id: int,
    options: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for option_id, option_text in options:
        builder.row(
            InlineKeyboardButton(
                text=option_text,
                callback_data=f"a:{attempt_id}:{question_id}:{option_id}",
            )
        )
    return builder.as_markup()
