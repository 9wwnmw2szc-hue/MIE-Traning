from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.keyboards.reply import BTN_HELP
from app.utils import texts

router = Router(name="help")


@router.message(Command("help"))
@router.message(F.text == BTN_HELP)
async def help_handler(message: Message) -> None:
    await message.answer(texts.HELP_TEXT)
