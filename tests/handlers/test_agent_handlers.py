import datetime
from unittest.mock import AsyncMock

import pytest
from aiogram.types import User, Chat, Message
from sqlmodel import Session

from app.handlers.agent_handlers import handle_close_chat_command, handle_agent_message
from app.models.models import SupportSession, SupportAgent
from app.services import session_service


@pytest.mark.asyncio
async def test_close_chat_success(session: Session, mocker):
    """
    Тест: Агент успешно закрывает назначенную на него сессию.
    """
    # Arrange
    mock_bot = AsyncMock()
    mocker.patch.object(session_service, "close_session", return_value=True)

    agent = SupportAgent(telegram_id=456, is_active=True, is_available=False)
    active_session = SupportSession(
        user_telegram_id=123,
        agent_telegram_id=agent.telegram_id,
        topic_id=101,
        status="active",
    )
    session.add(agent)
    session.add(active_session)
    session.commit()

    message = Message(
        message_id=1,
        chat=Chat(id=-100, type="supergroup"),
        from_user=User(id=agent.telegram_id, is_bot=False, first_name="Agent"),
        message_thread_id=active_session.topic_id,
        text="/close_chat",
        date=datetime.datetime.now(),
        bot=mock_bot,
    )
    mocker.patch("aiogram.types.Message.reply", new_callable=AsyncMock)

    # Act
    await handle_close_chat_command(message, bot=mock_bot, session=session)

    # Assert
    session_service.close_session.assert_awaited_once()
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=active_session.user_telegram_id,
        text="✅ Ваша сессия поддержки была завершена оператором. Спасибо за обращение!",
    )


@pytest.mark.asyncio
async def test_close_chat_wrong_agent(session: Session, mocker):
    """
    Тест: Агент пытается закрыть сессию, назначенную на другого агента.
    """
    # Arrange
    mock_bot = AsyncMock()
    mocker.patch.object(session_service, "close_session")

    assigned_agent = SupportAgent(telegram_id=456, is_active=True)
    another_agent = SupportAgent(telegram_id=789, is_active=True)
    active_session = SupportSession(
        user_telegram_id=123, agent_telegram_id=assigned_agent.telegram_id, topic_id=101
    )
    session.add_all([assigned_agent, another_agent, active_session])
    session.commit()

    message = Message(
        message_id=1,
        chat=Chat(id=-100, type="supergroup"),
        from_user=User(
            id=another_agent.telegram_id, is_bot=False, first_name="Wrong Agent"
        ),
        message_thread_id=active_session.topic_id,
        text="/close_chat",
        date=datetime.datetime.now(),
        bot=mock_bot,
    )
    reply_mock = mocker.patch("aiogram.types.Message.reply", new_callable=AsyncMock)

    # Act
    await handle_close_chat_command(message, bot=mock_bot, session=session)

    # Assert
    session_service.close_session.assert_not_awaited()
    reply_mock.assert_awaited_once_with(
        "⛔️ Вы не можете закрыть эту сессию, так как она назначена на другого агента."
    )


@pytest.mark.asyncio
async def test_agent_message_forwarded_to_user(session: Session, mocker):
    """
    Тест: Сообщение от назначенного агента успешно пересылается пользователю.
    """
    # Arrange
    mock_bot = AsyncMock()
    agent = SupportAgent(telegram_id=456, is_active=True)
    active_session = SupportSession(
        user_telegram_id=123, agent_telegram_id=agent.telegram_id, topic_id=101
    )
    session.add_all([agent, active_session])
    session.commit()

    message = Message(
        message_id=5,
        chat=Chat(id=-100, type="supergroup"),
        from_user=User(id=agent.telegram_id, is_bot=False, first_name="Agent"),
        message_thread_id=active_session.topic_id,
        text="Your answer is...",
        date=datetime.datetime.now(),
        bot=mock_bot,
    )

    # Act
    await handle_agent_message(message, bot=mock_bot, session=session)

    # Assert
    mock_bot.copy_message.assert_awaited_once_with(
        chat_id=active_session.user_telegram_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )


@pytest.mark.asyncio
async def test_agent_message_from_wrong_agent_ignored(session: Session, mocker):
    """
    Тест: Сообщение от другого агента (не назначенного) игнорируется.
    """
    # Arrange
    mock_bot = AsyncMock()
    assigned_agent = SupportAgent(telegram_id=456, is_active=True)
    another_agent = SupportAgent(telegram_id=789, is_active=True)
    active_session = SupportSession(
        user_telegram_id=123, agent_telegram_id=assigned_agent.telegram_id, topic_id=101
    )
    session.add_all([assigned_agent, another_agent, active_session])
    session.commit()

    message = Message(
        message_id=5,
        chat=Chat(id=-100, type="supergroup"),
        from_user=User(
            id=another_agent.telegram_id, is_bot=False, first_name="Wrong Agent"
        ),
        message_thread_id=active_session.topic_id,
        text="I'll take it from here",
        date=datetime.datetime.now(),
        bot=mock_bot,
    )

    # Act
    await handle_agent_message(message, bot=mock_bot, session=session)

    # Assert
    mock_bot.copy_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_message_in_topic_with_no_session_ignored(session: Session, mocker):
    """
    Тест: Сообщение в теме без активной сессии игнорируется.
    """
    # Arrange
    mock_bot = AsyncMock()
    agent = SupportAgent(telegram_id=456, is_active=True)
    session.add(agent)
    session.commit()

    message = Message(
        message_id=5,
        chat=Chat(id=-100, type="supergroup"),
        from_user=User(id=agent.telegram_id, is_bot=False, first_name="Agent"),
        message_thread_id=999,  # Несуществующая тема
        text="Hello?",
        date=datetime.datetime.now(),
        bot=mock_bot,
    )

    # Act
    await handle_agent_message(message, bot=mock_bot, session=session)

    # Assert
    mock_bot.copy_message.assert_not_awaited()
