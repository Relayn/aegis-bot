"""
Сервис для управления жизненным циклом сессий поддержки.
"""
import datetime
import logging
from typing import Optional

from aiogram import Bot
from sqlmodel import Session, select

from app.core.config import settings
from app.models.models import SupportAgent, SupportSession
from app.services import agent_service


async def create_new_session(
    session: Session, bot: Bot, user_telegram_id: int, user_username: Optional[str]
) -> Optional[SupportSession]:
    """
    Создает новую сессию поддержки.

    1. Находит свободного агента.
    2. Создает новую тему в супергруппе.
    3. Отправляет стартовое сообщение в тему.
    4. Сохраняет сессию в БД.

    :param session: Сессия базы данных.
    :param bot: Экземпляр aiogram Bot.
    :param user_telegram_id: ID пользователя, инициировавшего сессию.
    :param user_username: Username пользователя.
    :return: Созданный объект сессии или None, если не найден свободный агент или произошла ошибка.
    """
    logging.info(f"Attempting to create a new session for user {user_telegram_id}")

    # 1. Атомарно находим и блокируем свободного агента
    available_agent = agent_service.find_available_agent(session)
    if not available_agent:
        logging.warning(f"No available agents for new session request from user {user_telegram_id}")
        return None

    try:
        # 2. Создаем новую тему в супергруппе
        topic_name = f"Сессия с @{user_username or user_telegram_id}"
        topic = await bot.create_forum_topic(
            chat_id=settings.SUPERGROUP_ID,
            name=topic_name
        )
        logging.info(f"Created new topic {topic.message_thread_id} for user {user_telegram_id}")

        # 3. Отправляем системное сообщение в тему
        start_message = (
            f"✅ Новая сессия поддержки.\n\n"
            f"👤 **Пользователь:** <a href='tg://user?id={user_telegram_id}'>{user_username or user_telegram_id}</a>\n"
            f"🆔 **User ID:** `{user_telegram_id}`\n\n"
            f"🧑‍💻 **Назначенный агент:** @{available_agent.username or available_agent.telegram_id}"
        )
        await bot.send_message(
            chat_id=settings.SUPERGROUP_ID,
            message_thread_id=topic.message_thread_id,
            text=start_message
        )

        # 4. Сохраняем сессию в БД
        new_session = SupportSession(
            user_telegram_id=user_telegram_id,
            agent_telegram_id=available_agent.telegram_id,
            topic_id=topic.message_thread_id,
            status="active",
        )
        session.add(new_session)
        session.commit()
        session.refresh(new_session)
        logging.info(f"New session {new_session.id} created and saved to DB.")

        return new_session

    except Exception as e:
        logging.error(f"Failed to create topic or session for user {user_telegram_id}: {e}")
        # Если произошла ошибка (например, с API Telegram),
        # откатываем транзакцию, чтобы освободить агента.
        session.rollback()
        # Ищем агента заново, чтобы применить изменения
        agent_to_release = session.get(SupportAgent, available_agent.telegram_id)
        if agent_to_release:
            agent_to_release.is_available = True
            session.add(agent_to_release)
            session.commit()
            logging.info(f"Agent {agent_to_release.telegram_id} was released due to an error.")
        return None


async def close_session(session: Session, bot: Bot, active_session: SupportSession) -> bool:
    """
    Закрывает активную сессию поддержки.

    1. Удаляет тему из супергруппы.
    2. Обновляет статус сессии в БД на 'closed'.
    3. Освобождает агента, делая его доступным.

    :param session: Сессия базы данных.
    :param bot: Экземпляр aiogram Bot.
    :param active_session: Объект сессии, которую нужно закрыть.
    :return: True, если сессия успешно закрыта, иначе False.
    """
    logging.info(f"Attempting to close session {active_session.id} (topic {active_session.topic_id})")
    try:
        # 1. Удаляем тему из Telegram
        await bot.delete_forum_topic(
            chat_id=settings.SUPERGROUP_ID,
            message_thread_id=active_session.topic_id
        )
        logging.info(f"Topic {active_session.topic_id} deleted successfully.")

        # 2. Обновляем статус сессии в БД
        active_session.status = "closed"
        active_session.closed_at = datetime.datetime.now()
        session.add(active_session)

        # 3. Освобождаем агента
        agent = session.get(SupportAgent, active_session.agent_telegram_id)
        if agent:
            agent.is_available = True
            session.add(agent)
            logging.info(f"Agent {agent.telegram_id} is now available.")
        else:
            logging.warning(f"Could not find agent {active_session.agent_telegram_id} to make available.")

        session.commit()
        logging.info(f"Session {active_session.id} has been closed and saved to DB.")
        return True

    except Exception as e:
        logging.error(f"Failed to close session {active_session.id}: {e}")
        session.rollback()
        return False