"""
Обработчики для сообщений от агентов поддержки в супергруппе.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlmodel import Session, select

from app.core.config import settings
from app.models.models import SupportSession
from app.services import session_service

router = Router()
# Фильтруем сообщения: только из нашей супергруппы и только из тем (не из General)
router.message.filter(
    F.chat.id == settings.SUPERGROUP_ID, F.message_thread_id.is_not(None)
)


@router.message(Command("close_chat"))
async def handle_close_chat_command(message: Message, bot: Bot, session: Session):
    """
    Обрабатывает команду /close_chat от агента для завершения сессии.
    Получает сессию БД через middleware.
    """
    agent_id = message.from_user.id
    topic_id = message.message_thread_id

    statement = select(SupportSession).where(
        SupportSession.topic_id == topic_id, SupportSession.status == "active"
    )
    active_session = session.exec(statement).first()

    if not active_session:
        await message.reply("⚠️ Не найдено активной сессии в этой теме.")
        return

    # Проверяем, что команду дает именно назначенный агент
    if active_session.agent_telegram_id != agent_id:
        await message.reply(
            "⛔️ Вы не можете закрыть эту сессию, так как она назначена на другого агента."
        )
        return

    # Закрываем сессию через сервис
    success = await session_service.close_session(
        session=session, bot=bot, active_session=active_session
    )

    if success:
        # Уведомляем пользователя
        await bot.send_message(
            chat_id=active_session.user_telegram_id,
            text="✅ Ваша сессия поддержки была завершена оператором. Спасибо за обращение!",
        )
        # Сообщение в теме удалится вместе с самой темой.
    else:
        await message.reply(
            "🔴 Произошла ошибка при закрытии сессии. Попробуйте снова."
        )


@router.message()
async def handle_agent_message(message: Message, bot: Bot, session: Session):
    """
    Обрабатывает сообщение от агента в теме и пересылает его пользователю.
    Получает сессию БД через middleware.
    """
    agent_id = message.from_user.id
    topic_id = message.message_thread_id

    # 1. Находим сессию по ID темы
    statement = select(SupportSession).where(
        SupportSession.topic_id == topic_id, SupportSession.status == "active"
    )
    active_session = session.exec(statement).first()

    if not active_session:
        logging.warning(
            f"Received message in topic {topic_id}, but no active session found."
        )
        return

    # 2. Проверяем, что пишет именно назначенный на сессию агент
    if active_session.agent_telegram_id != agent_id:
        logging.warning(
            f"Agent {agent_id} tried to write to session {active_session.id} "
            f"of agent {active_session.agent_telegram_id}. Denied."
        )
        return

    # 3. Пересылаем копию сообщения пользователю
    logging.info(
        f"Copying message from agent {agent_id} to user {active_session.user_telegram_id}"
    )
    try:
        await bot.copy_message(
            chat_id=active_session.user_telegram_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception as e:
        logging.error(
            f"Failed to copy message to user {active_session.user_telegram_id}: {e}"
        )
        await message.reply(
            "🔴 **Ошибка доставки!**\n"
            "Не удалось доставить сообщение пользователю. "
            "Возможно, он заблокировал бота. Сессия остается открытой."
        )
