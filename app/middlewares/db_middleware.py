from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.session import get_session


class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware для внедрения сессии базы данных в хэндлеры.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Выполняется для каждого входящего события.

        Создает сессию с помощью `get_session` и передает ее в `data`.
        Гарантирует закрытие сессии после выполнения хэндлера.
        """
        with next(get_session()) as session:
            data["session"] = session
            return await handler(event, data)
