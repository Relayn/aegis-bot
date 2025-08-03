"""
Обработчики для сообщений от пользователей.
"""

import asyncio
import logging
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlmodel import Session, select

from app.core.config import settings
from app.models.models import SupportSession
from app.services import session_service

router = Router()
router.message.filter(F.chat.type == "private")

# Словарь для хранения блокировок для каждого пользователя.
# Это предотвращает состояние гонки при одновременном создании сессии.
user_locks = defaultdict(asyncio.Lock)


@router.message()
async def handle_user_message(message: Message, bot: Bot, session: Session):
    """
    Обрабатывает все сообщения от пользователя в личном чате.

    Использует asyncio.Lock для предотвращения создания нескольких сессий
    для одного пользователя одновременно.
    Получает сессию БД через middleware.
    """
    user_id = message.from_user.id

    # Захватываем блокировку для конкретного пользователя
    async with user_locks[user_id]:
        # 1. Проверяем, есть ли у пользователя активная сессия
        statement = select(SupportSession).where(
            SupportSession.user_telegram_id == user_id,
            SupportSession.status == "active",
        )
        active_session = session.exec(statement).first()

        if active_session:
            # 2. Если сессия есть, пересылаем сообщение в тему
            logging.info(
                f"Forwarding message from user {user_id} to topic {active_session.topic_id}"
            )
            await bot.forward_message(
                chat_id=settings.SUPERGROUP_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=active_session.topic_id,
            )
        else:
            # 3. Если сессии нет, создаем новую
            logging.info(f"No active session for user {user_id}. Creating a new one.")
            new_session = await session_service.create_new_session(
                session=session,
                bot=bot,
                user_telegram_id=user_id,
                user_username=message.from_user.username,
            )

            if new_session:
                await message.answer(
                    "✅ Оператор поддержки скоро подключится к вашему чату. "
                    "Пожалуйста, ожидайте."
                )
                # Пересылаем первое сообщение, которое инициировало сессию
                await bot.forward_message(
                    chat_id=settings.SUPERGROUP_ID,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    message_thread_id=new_session.topic_id,
                )
            else:
                await message.answer(
                    "К сожалению, все операторы сейчас заняты. "
                    "Пожалуйста, попробуйте написать позже."
                )
