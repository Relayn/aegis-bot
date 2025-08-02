from sqlmodel import Session

from app.models.models import SupportAgent
from app.services.agent_service import find_available_agent


# --- Тесты для функции find_available_agent ---


def test_find_available_agent_success(session: Session):
    """
    Позитивный случай: есть один доступный агент.
    Ожидаем, что функция его найдет и пометит как недоступного.
    """
    # Arrange: Создаем агента в БД
    available_agent = SupportAgent(telegram_id=123, is_available=True, is_active=True)
    session.add(available_agent)
    session.commit()

    # Act: Вызываем тестируемую функцию
    found_agent = find_available_agent(session)

    # Assert: Проверяем результат
    assert found_agent is not None
    assert found_agent.telegram_id == 123
    # Самая важная проверка: статус агента в БД должен был измениться
    agent_in_db = session.get(SupportAgent, 123)
    assert agent_in_db.is_available is False


def test_find_available_agent_no_agents_in_db(session: Session):
    """
    Негативный случай: в базе данных вообще нет агентов.
    Ожидаем, что функция вернет None.
    """
    # Arrange: БД пуста

    # Act: Вызываем функцию
    found_agent = find_available_agent(session)

    # Assert: Проверяем, что ничего не найдено
    assert found_agent is None


def test_find_available_agent_no_available_agents(session: Session):
    """
    Негативный случай: все агенты заняты (is_available = False).
    Ожидаем, что функция вернет None.
    """
    # Arrange: Создаем только занятых агентов
    busy_agent_1 = SupportAgent(telegram_id=1, is_available=False, is_active=True)
    busy_agent_2 = SupportAgent(telegram_id=2, is_available=False, is_active=True)
    session.add(busy_agent_1)
    session.add(busy_agent_2)
    session.commit()

    # Act: Вызываем функцию
    found_agent = find_available_agent(session)

    # Assert: Проверяем, что ничего не найдено
    assert found_agent is None


def test_find_available_agent_no_active_agents(session: Session):
    """
    Негативный случай: все агенты неактивны (is_active = False).
    Ожидаем, что функция вернет None.
    """
    # Arrange: Создаем только неактивных агентов
    inactive_agent = SupportAgent(telegram_id=1, is_available=True, is_active=False)
    session.add(inactive_agent)
    session.commit()

    # Act: Вызываем функцию
    found_agent = find_available_agent(session)

    # Assert: Проверяем, что ничего не найдено
    assert found_agent is None


def test_find_available_agent_selects_only_one(session: Session):
    """
    Граничный случай: есть несколько свободных агентов.
    Ожидаем, что функция выберет только одного и заблокирует его.
    """
    # Arrange: Создаем несколько свободных агентов
    agent1 = SupportAgent(telegram_id=1, is_available=True, is_active=True)
    agent2 = SupportAgent(telegram_id=2, is_available=True, is_active=True)
    session.add(agent1)
    session.add(agent2)
    session.commit()

    # Act: Вызываем функцию
    found_agent = find_available_agent(session)

    # Assert: Проверяем, что агент найден и он один
    assert found_agent is not None
    # Проверяем, что статус именно этого агента изменился
    agent_in_db = session.get(SupportAgent, found_agent.telegram_id)
    assert agent_in_db.is_available is False
    # Проверяем, что статус второго агента НЕ изменился
    other_agent_id = 1 if found_agent.telegram_id == 2 else 2
    other_agent_in_db = session.get(SupportAgent, other_agent_id)
    assert other_agent_in_db.is_available is True
