import datetime
from unittest.mock import AsyncMock

import pytest
from aiogram.types import User, Chat, Message
from sqlmodel import Session

from app.handlers.user_handlers import handle_user_message
from app.models.models import SupportSession
from app.services import session_service


@pytest.mark.asyncio
async def test_start_new_session_handler_success(session: Session, mocker):
    """
    Тест на успешное создание новой сессии через хэндлер.
    """
    # Arrange
    mocker.patch.object(
        session_service,
        "create_new_session",
        return_value=SupportSession(
            id=1, topic_id=100, user_telegram_id=123, agent_telegram_id=456
        ),
    )
    mock_bot = AsyncMock()
    answer_mock = mocker.patch("aiogram.types.Message.answer", new_callable=AsyncMock)

    mock_message = Message(
        message_id=1,
        chat=Chat(id=123, type="private"),
        from_user=User(id=123, is_bot=False, first_name="John"),
        text="Hello",
        date=datetime.datetime.now(),
        bot=mock_bot,
    )

    # Act
    await handle_user_message(mock_message, bot=mock_bot, session=session)

    # Assert
    answer_mock.assert_awaited_with(
        "✅ Оператор поддержки скоро подключится к вашему чату. Пожалуйста, ожидайте."
    )
    mock_bot.forward_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_forward_message_in_existing_session(session: Session, mocker):
    """
    Тест на пересылку сообщения в уже существующую сессию.
    """
    # Arrange
    mock_bot = AsyncMock()
    user = User(id=123, is_bot=False, first_name="John")
    chat = Chat(id=123, type="private")
    mocker.patch("app.handlers.user_handlers.settings.SUPERGROUP_ID", -100987654321)
    session.add(
        SupportSession(
            user_telegram_id=user.id,
            agent_telegram_id=456,
            topic_id=101,
            status="active",
        )
    )
    session.commit()

    answer_mock = mocker.patch("aiogram.types.Message.answer", new_callable=AsyncMock)

    message = Message(
        message_id=2,
        chat=chat,
        from_user=user,
        text="One more thing",
        date=datetime.datetime.now(),
        bot=mock_bot,
    )

    # Act
    await handle_user_message(message, bot=mock_bot, session=session)

    # Assert
    mock_bot.forward_message.assert_awaited_once_with(
        chat_id=-100987654321, from_chat_id=123, message_id=2, message_thread_id=101
    )
    answer_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_new_session_no_agents_available(session: Session, mocker):
    """
    Тест: Пользователь пишет, но нет свободных агентов.
    """
    # Arrange
    mocker.patch.object(session_service, "create_new_session", return_value=None)
    mock_bot = AsyncMock()
    answer_mock = mocker.patch("aiogram.types.Message.answer", new_callable=AsyncMock)

    mock_message = Message(
        message_id=1,
        chat=Chat(id=123, type="private"),
        from_user=User(id=123, is_bot=False, first_name="John"),
        text="Hello",
        date=datetime.datetime.now(),
        bot=mock_bot,
    )

    # Act
    await handle_user_message(mock_message, bot=mock_bot, session=session)

    # Assert
    answer_mock.assert_awaited_with(
        "К сожалению, все операторы сейчас заняты. "
        "Пожалуйста, попробуйте написать позже."
    )
    mock_bot.forward_message.assert_not_awaited()
