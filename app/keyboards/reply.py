from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_START_TEST = "Начать тест"
BTN_CONTINUE_TEST = "Продолжить тест"
BTN_MY_RESULTS = "Мои результаты"
BTN_HELP = "Помощь"
BTN_RETRY = "Пройти тест ещё раз"
BTN_SHOW_ERRORS = "Посмотреть ошибки"
BTN_MAIN_MENU = "Главное меню"
BTN_CONTINUE = "Продолжить тест"
BTN_RESTART = "Начать заново"
BTN_CANCEL = "Отмена"


def main_menu_keyboard(*, has_active_attempt: bool = False) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if has_active_attempt:
        rows.append([KeyboardButton(text=BTN_CONTINUE_TEST)])
    rows.extend(
        [
            [KeyboardButton(text=BTN_START_TEST)],
            [KeyboardButton(text=BTN_MY_RESULTS), KeyboardButton(text=BTN_HELP)],
        ]
    )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def finish_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_RETRY)],
            [KeyboardButton(text=BTN_SHOW_ERRORS)],
            [KeyboardButton(text=BTN_MAIN_MENU)],
        ],
        resize_keyboard=True,
    )


def active_test_conflict_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CONTINUE)],
            [KeyboardButton(text=BTN_RESTART)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )
