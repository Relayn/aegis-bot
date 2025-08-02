import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import settings
from app.db.session import create_db_and_tables, get_session
from app.services.agent_service import sync_agents_from_env
from app.handlers import agent_handlers, user_handlers


async def main() -> None:
    """Главная функция для запуска бота."""
    logging.info("Initializing database and tables...")
    create_db_and_tables()
    logging.info("Database initialized successfully.")

    # Синхронизация агентов при старте
    with next(get_session()) as session:
        sync_agents_from_env(session)

        # Инициализация бота и диспетчера
    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(user_handlers.router)
    dp.include_router(agent_handlers.router)

    logging.info("Starting bot...")
    # Запуск long polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    # Настройка базового логирования
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
        raise