from functools import partial
from typing import Callable
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from tgbot.filters.chat import IsPrivate
from tgbot.keyboards.inline import (
    support_menu,
)
from tgbot.keyboards.reply import main_menu

user_router = Router()
user_router.message.filter(IsPrivate())


@user_router.callback_query(F.data == "cancel")
async def cancel_current(call: CallbackQuery, state: FSMContext):
    await state.clear()
    if call.message and not isinstance(call.message, InaccessibleMessage):
        await call.message.delete()
    await call.answer("Canceled")


@user_router.message(CommandStart())
async def user_start(message: Message):
    if not message.from_user:
        return

    await message.answer(
        "Welcome to the Bot!",
        reply_markup=main_menu,
    )


@user_router.message(F.text == "❗️Info")
async def support_handler(message: Message):
    await message.answer(
        "Contact support⤵️",
        reply_markup=support_menu,
    )


@user_router.callback_query(F.data == "personal_acc")
@user_router.message(F.text == "👤Profile")
async def personal_acc_handler(event: Message | CallbackQuery):
    send_method: Callable = partial(
        event.message.edit_text if isinstance(event, CallbackQuery) else event.answer
    )
    await send_method(
        f"Profile\n"
        f"├─ID: <code>{event.from_user.id}</>\n"
        f"└─Username: <code>{event.from_user.username}</>"
    )
