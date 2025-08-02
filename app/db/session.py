"""
Модуль для управления сессиями базы данных.
"""
from sqlmodel import Session, SQLModel, create_engine

from app.models import models

# Имя файла базы данных будет в корне проекта для простоты доступа
DATABASE_FILE = "aegis_bot.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# connect_args={"check_same_thread": False} - обязательный флаг для SQLite
# при работе с асинхронными фреймворками, такими как aiogram.
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})


def create_db_and_tables():
    """
    Создает файл базы данных и все таблицы.

    Вызывается один раз при старте приложения.
    """
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Зависимость (dependency) для получения сессии БД.

    Использует `yield` для гарантии закрытия сессии после использования.
    """
    with Session(engine) as session:
        yield session