from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def answers_keyboard(
    attempt_id: int,
    question_id: int,
    options: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    """
    options: list of (option_id, button_label)
    Button labels must be short (<=64 chars) for Telegram.
    """
    builder = InlineKeyboardBuilder()
    row: list[InlineKeyboardButton] = []
    for option_id, option_text in options:
        label = option_text if len(option_text) <= 64 else option_text[:61] + "..."
        row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"a:{attempt_id}:{question_id}:{option_id}",
            )
        )
        if len(row) == 2:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    return builder.as_markup()
