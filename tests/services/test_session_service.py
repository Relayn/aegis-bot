from unittest.mock import AsyncMock

import pytest
from aiogram.types import ForumTopic, User
from sqlmodel import Session

from app.models.models import SupportAgent
from app.services.session_service import create_new_session

# --- Тесты для функции create_new_session ---


@pytest.mark.asyncio
async def test_create_new_session_success(session: Session):
    """
    Позитивный случай: успешное создание новой сессии.
    Проверяем, что все вызовы API сделаны и данные в БД корректны.
    """
    # Arrange:
    # 1. Создаем мок-объект бота и его методы
    mock_bot = AsyncMock()
    # Мокаем ответ от create_forum_topic
    mock_bot.create_forum_topic.return_value = ForumTopic(
        message_thread_id=100, name="Test Topic", icon_color=1
    )

    # 2. Создаем пользователя и агента в БД
    user = User(id=123, is_bot=False, first_name="Test")
    agent = SupportAgent(telegram_id=456, is_available=True, is_active=True)
    session.add(agent)
    session.commit()

    # Act: Вызываем тестируемую функцию
    new_session = await create_new_session(
        session=session,
        bot=mock_bot,
        user_telegram_id=user.id,
        user_username=user.first_name,
    )

    # Assert:
    # 1. Проверяем, что сессия создана и возвращена
    assert new_session is not None
    assert new_session.user_telegram_id == user.id
    assert new_session.agent_telegram_id == agent.telegram_id
    assert new_session.topic_id == 100
    assert new_session.status == "active"

    # 2. Проверяем, что агент в БД теперь занят
    agent_in_db = session.get(SupportAgent, agent.telegram_id)
    assert agent_in_db.is_available is False

    # 3. Проверяем, что методы бота были вызваны с правильными аргументами
    mock_bot.create_forum_topic.assert_awaited_once()
    mock_bot.send_message.assert_awaited_once()
    # Проверяем, что системное сообщение было отправлено в созданную тему
    assert mock_bot.send_message.call_args.kwargs["message_thread_id"] == 100


@pytest.mark.asyncio
async def test_create_new_session_no_available_agents(session: Session):
    """
    Негативный случай: нет свободных агентов.
    Ожидаем, что сессия не будет создана, и API бота не будет вызвано.
    """
    # Arrange:
    # 1. Создаем мок-объект бота
    mock_bot = AsyncMock()
    # 2. БД не содержит агентов или все заняты
    user = User(id=123, is_bot=False, first_name="Test")

    # Act:
    new_session = await create_new_session(
        session=session,
        bot=mock_bot,
        user_telegram_id=user.id,
        user_username=user.first_name,
    )

    # Assert:
    # 1. Проверяем, что сессия не создана
    assert new_session is None
    # 2. Проверяем, что API для создания темы НЕ вызывалось
    mock_bot.create_forum_topic.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_new_session_api_error_rollbacks_agent_status(session: Session):
    """
    Граничный случай: агент найден, но происходит ошибка при создании темы в Telegram.
    Ожидаем, что статус агента будет откачен к is_available=True.
    """
    # Arrange:
    # 1. Настраиваем мок бота так, чтобы он вызывал исключение
    mock_bot = AsyncMock()
    mock_bot.create_forum_topic.side_effect = Exception("Telegram API Error")

    # 2. Создаем доступного агента
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
    # 1. Проверяем, что сессия не создана
    assert new_session is None
    # 2. Самая важная проверка: проверяем, что статус агента в БД был откачен
    agent_in_db = session.get(SupportAgent, agent.telegram_id)
    assert agent_in_db.is_available is True
