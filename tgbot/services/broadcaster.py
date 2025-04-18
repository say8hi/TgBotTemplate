import asyncio
import logging
from typing import List, Optional, Union

from aiogram import Bot
from aiogram import exceptions
from aiogram.types import InlineKeyboardMarkup

from tgbot.database.models import User


async def send_message(
    bot: Bot,
    user_id: Union[int, str],
    text: str,
    disable_notification: bool = False,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    """
    Safe messages sender

    :param bot: Bot instance.
    :param user_id: user id. If str - must contain only digits.
    :param text: text of the message.
    :param disable_notification: disable notification or not.
    :param reply_markup: reply markup.
    :return: success.
    """
    try:
        await bot.send_message(
            user_id,
            text,
            disable_notification=disable_notification,
            reply_markup=reply_markup,
        )
    except exceptions.TelegramBadRequest as e:
        logging.error("Telegram server says - Bad Request: chat not found")
    except exceptions.TelegramForbiddenError:
        logging.error(f"Target [ID:{user_id}]: got TelegramForbiddenError")
    except exceptions.TelegramRetryAfter as e:
        logging.error(
            f"Target [ID:{user_id}]: Flood limit is exceeded. Sleep {e.retry_after} seconds."
        )
        await asyncio.sleep(e.retry_after)
        return await send_message(
            bot, user_id, text, disable_notification, reply_markup
        )  # Recursive call
    except exceptions.TelegramAPIError:
        logging.exception(f"Target [ID:{user_id}]: failed")
    else:
        logging.info(f"Target [ID:{user_id}]: success")
        return True
    return False


async def broadcast(
    bot: Bot,
    users: List[User],
    text: Optional[str] = "",
    photo_id: Optional[str] = None,
    disable_notification: bool = False,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> int:
    count = 0
    try:
        for user in users:
            if not photo_id:
                if await send_message(
                    bot,
                    user.id if isinstance(user, User) else user,
                    text,
                    disable_notification,
                    reply_markup,
                ):
                    count += 1
            else:
                try:
                    await bot.send_photo(
                        user.id if isinstance(user, User) else user,
                        photo=photo_id,
                        caption=text,
                        disable_notification=disable_notification,
                        reply_markup=reply_markup,
                    )
                    count += 1
                except Exception:
                    pass
            await asyncio.sleep(0.05)
    finally:
        logging.info(f"BROADCAST: {count} messages successful sent.")

    return count
