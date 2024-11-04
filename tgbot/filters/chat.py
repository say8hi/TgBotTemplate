from aiogram.filters import BaseFilter
from aiogram.types import Message


class IsPrivate(BaseFilter):
    async def __call__(self, obj: Message) -> bool:
        return obj.chat.type == "private"
