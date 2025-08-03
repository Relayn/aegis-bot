from unittest.mock import AsyncMock

import pytest
from aiogram.types import ForumTopic, User
from sqlmodel import Session

from app.models.models import SupportAgent, SupportSession
from app.services.session_service import create_new_session, close_session


# --- Тесты для функции create_new_session ---


@pytest.mark.asyncio
async def test_create_new_session_success(session: Session):
    """
    Позитивный случай: успешное создание новой сессии.
    Проверяем, что все вызовы API сделаны и данные в БД корректны.
    """
    # Arrange:
    mock_bot = AsyncMock()
    mock_bot.create_forum_topic.return_value = ForumTopic(
        message_thread_id=100, name="Test Topic", icon_color=1
    )
    user = User(id=123, is_bot=False, first_name="Test")
    agent = SupportAgent(telegram_id=456, is_available=True, is_active=True)
    session.add(agent)
    session.commit()

    # Act:
    new_session = await create_new_session(
        session=session,
        bot=mock_bot,
        user_telegram_id=user.id,
        user_username=user.first_name,
    )

    # Assert:
    assert new_session is not None
    assert new_session.user_telegram_id == user.id
    assert new_session.agent_telegram_id == agent.telegram_id
    assert new_session.topic_id == 100
    agent_in_db = session.get(SupportAgent, agent.telegram_id)
    assert agent_in_db.is_available is False
    mock_bot.create_forum_topic.assert_awaited_once()
    mock_bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_new_session_no_available_agents(session: Session):
    """
    Негативный случай: нет свободных агентов.
    """
    # Arrange:
    mock_bot = AsyncMock()
    user = User(id=123, is_bot=False, first_name="Test")

    # Act:
    new_session = await create_new_session(
        session=session,
        bot=mock_bot,
        user_telegram_id=user.id,
        user_username=user.first_name,
    )

    # Assert:
    assert new_session is None
    mock_bot.create_forum_topic.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_new_session_api_error_rollbacks_agent_status(session: Session):
    """
    Граничный случай: ошибка API Telegram откатывает статус агента.
    """
    # Arrange:
    mock_bot = AsyncMock()
    mock_bot.create_forum_topic.side_effect = Exception("Telegram API Error")
    agent = SupportAgent(telegram_id=456, is_available=True, is_active=True)
    session.add(agent)
    session.commit()
    user = User(id=123, is_bot=False, first_name="Test")

    # Act:
    new_session = await create_new_session(
        session=session,
        bot=mock_bot,
        user_telegram_id=user.id,
        user_username=user.first_name,
    )

    # Assert:
    assert new_session is None
    agent_in_db = session.get(SupportAgent, agent.telegram_id)
    assert agent_in_db.is_available is True


# --- Тесты для функции close_session ---


@pytest.mark.asyncio
async def test_close_session_success(session: Session, mocker):
    """
    Позитивный случай: успешное закрытие сессии.
    """
    # Arrange
    mock_bot = AsyncMock()
    # Мокаем ID группы, чтобы тест не зависел от .env файла
    mocker.patch("app.services.session_service.settings.SUPERGROUP_ID", -100999888)

    agent = SupportAgent(telegram_id=456, is_available=False, is_active=True)
    active_session = SupportSession(
        user_telegram_id=123,
        agent_telegram_id=agent.telegram_id,
        topic_id=101,
        status="active",
    )
    session.add(agent)
    session.add(active_session)
    session.commit()

    # Act
    result = await close_session(session, mock_bot, active_session)

    # Assert
    assert result is True
    mock_bot.delete_forum_topic.assert_awaited_once_with(
        chat_id=-100999888,  # Проверяем с мокнутым значением
        message_thread_id=active_session.topic_id,
    )
    session.refresh(agent)
    session.refresh(active_session)
    assert agent.is_available is True
    assert active_session.status == "closed"
    assert active_session.closed_at is not None


@pytest.mark.asyncio
async def test_close_session_api_error_rollbacks_db(session: Session):
    """
    Негативный случай: ошибка API Telegram откатывает изменения в БД.
    """
    # Arrange
    mock_bot = AsyncMock()
    mock_bot.delete_forum_topic.side_effect = Exception("Telegram API Error")
    agent = SupportAgent(telegram_id=456, is_available=False, is_active=True)
    active_session = SupportSession(
        user_telegram_id=123,
        agent_telegram_id=agent.telegram_id,
        topic_id=101,
        status="active",
    )
    session.add(agent)
    session.add(active_session)
    session.commit()

    # Act
    result = await close_session(session, mock_bot, active_session)

    # Assert
    assert result is False
    # Обновляем объекты из сессии, чтобы увидеть, были ли изменения
    session.refresh(agent)
    session.refresh(active_session)
    assert agent.is_available is False  # Статус не должен был измениться
    assert active_session.status == "active"  # Статус не должен был измениться
