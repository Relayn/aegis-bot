"""
Модуль конфигурации проекта.

Загружает настройки из переменных окружения и .env файла.
Использует Pydantic V2 для валидации данных.
"""
from typing import List

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс для хранения и валидации настроек приложения.
    """
    # Модель для загрузки переменных из .env файла
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --- Telegram Bot Settings ---
    BOT_TOKEN: SecretStr
    ADMIN_ID: int

    # --- Support Group Settings ---
    SUPERGROUP_ID: int
    AGENT_IDS: str  # Ожидается строка с ID через запятую, например "123,456"

    @field_validator("AGENT_IDS")
    @classmethod
    def parse_agent_ids(cls, v: str) -> List[int]:
        """Валидирует и преобразует строку ID агентов в список чисел."""
        if not v:
            raise ValueError("AGENT_IDS не может быть пустым.")
        try:
            return [int(agent_id.strip()) for agent_id in v.split(",")]
        except ValueError:
            raise ValueError("AGENT_IDS должен содержать только числа, разделенные запятой.")


# Создаем единственный экземпляр настроек для всего приложения
settings = Settings()