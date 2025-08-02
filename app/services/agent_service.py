"""
Сервис для управления агентами поддержки.
"""
import logging
from typing import Optional

from sqlmodel import Session, select

from app.core.config import settings
from app.models.models import SupportAgent


def sync_agents_from_env(session: Session) -> None:
    """
    Синхронизирует список агентов в БД со списком из переменных окружения.

    - Добавляет новых агентов.
    - Активирует существующих агентов, если они есть в .env.
    - Деактивирует агентов, которых убрали из .env.
    """
    logging.info("Starting agent synchronization from .env file...")
    env_agent_ids = set(settings.AGENT_IDS)

    # 1. Получаем всех агентов из БД
    statement = select(SupportAgent)
    db_agents = session.exec(statement).all()
    db_agent_ids = {agent.telegram_id for agent in db_agents}

    # 2. Находим ID для добавления и для обновления
    ids_to_add = env_agent_ids - db_agent_ids
    ids_to_deactivate = db_agent_ids - env_agent_ids
    ids_to_reactivate = env_agent_ids & db_agent_ids

    # 3. Добавляем новых агентов
    for agent_id in ids_to_add:
        new_agent = SupportAgent(telegram_id=agent_id, is_active=True, is_available=True)
        session.add(new_agent)
        logging.info(f"Added new agent with ID: {agent_id}")

    # 4. Обновляем статус существующих агентов
    for agent in db_agents:
        # Деактивируем агента, только если он есть в списке на деактивацию И он сейчас активен
        if agent.telegram_id in ids_to_deactivate and agent.is_active:
            agent.is_active = False
            session.add(agent)
            logging.info(f"Deactivated agent with ID: {agent.telegram_id}")
        # Реактивируем агента, только если он есть в списке на реактивацию И он сейчас неактивен
        elif agent.telegram_id in ids_to_reactivate and not agent.is_active:
            agent.is_active = True
            session.add(agent)
            logging.info(f"Reactivated agent with ID: {agent.telegram_id}")

    session.commit()
    logging.info("Agent synchronization finished.")


def find_available_agent(session: Session) -> Optional[SupportAgent]:
    """
    Находит доступного агента и атомарно помечает его как занятого.

    Использует 'SELECT ... FOR UPDATE' для предотвращения состояния гонки.
    :param session: Сессия базы данных.
    :return: Объект SupportAgent или None, если свободных агентов нет.
    """
    statement = (
        select(SupportAgent)
        .where(SupportAgent.is_available == True, SupportAgent.is_active == True)
        .limit(1)
        .with_for_update()  # Блокируем найденную строку до конца транзакции
    )
    agent = session.exec(statement).first()

    if agent:
        logging.info(f"Found available agent: {agent.telegram_id}. Locking for session.")
        agent.is_available = False
        session.add(agent)
        session.commit()
        session.refresh(agent)  # Обновляем объект из БД
        logging.info(f"Agent {agent.telegram_id} is now marked as unavailable.")
        return agent

    logging.warning("No available agents found.")
    return None