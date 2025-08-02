"""
Модуль с моделями данных для базы данных.

Определяет таблицы SupportAgent и SupportSession с использованием SQLModel.
"""
import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SupportAgent(SQLModel, table=True):
    """
    Модель агента поддержки.
    """
    telegram_id: int = Field(primary_key=True, description="Telegram User ID агента")
    username: Optional[str] = Field(default=None, description="Telegram @username агента")
    is_available: bool = Field(default=True, index=True, description="Доступен ли агент для новых сессий")
    is_active: bool = Field(default=True, index=True, description="Активен ли агент в системе")


class SupportSession(SQLModel, table=True):
    """
    Модель сессии поддержки.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_telegram_id: int = Field(index=True, description="Telegram User ID клиента")
    agent_telegram_id: int = Field(foreign_key="supportagent.telegram_id", description="ID назначенного агента")
    topic_id: int = Field(unique=True, description="ID темы (topic) в супергруппе")
    status: str = Field(index=True, default="active", description="Статус сессии: active, closed")
    created_at: datetime.datetime = Field(
        default_factory=datetime.datetime.now,
        description="Время создания сессии"
    )
    closed_at: Optional[datetime.datetime] = Field(default=None, description="Время закрытия сессии")