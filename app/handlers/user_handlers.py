"""
Обработчики для сообщений от пользователей.
"""
import logging

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlmodel import select

from app.core.config import settings
from app.db.session import get_session
from app.models.models import SupportSession
from app.services import session_service

router = Router()
# Этот фильтр гарантирует, что хэндлеры в этом роутере
# будут срабатывать только в личных чатах с ботом.
router.message.filter(F.chat.type == "private")


@router.message()
async def handle_user_message(message: Message, bot: Bot):
    """
    Обрабатывает все сообщения от пользователя в личном чате.

    - Если активной сессии нет, создает новую.
    - Если сессия есть, пересылает сообщение в соответствующую тему.
    """
    user_id = message.from_user.id
    user_username = message.from_user.username

    with next(get_session()) as session:
        # 1. Проверяем, есть ли у пользователя активная сессия
        statement = select(SupportSession).where(
            SupportSession.user_telegram_id == user_id,
            SupportSession.status == "active"
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
                message_thread_id=active_session.topic_id
            )
        else:
            # 3. Если сессии нет, создаем новую
            logging.info(f"No active session for user {user_id}. Creating a new one.")
            new_session = await session_service.create_new_session(
                session=session,
                bot=bot,
                user_telegram_id=user_id,
                user_username=user_username
            )

            if new_session:
                # Отправляем пользователю подтверждение
                await message.answer(
                    "✅ Оператор поддержки скоро подключится к вашему чату. "
                    "Пожалуйста, ожидайте."
                )
                # Пересылаем первое сообщение, которое инициировало сессию
                await bot.forward_message(
                    chat_id=settings.SUPERGROUP_ID,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    message_thread_id=new_session.topic_id
                )
            else:
                # Если создать сессию не удалось (нет свободных агентов)
                await message.answer(
                    "К сожалению, все операторы сейчас заняты. "
                    "Пожалуйста, попробуйте написать позже."
                )