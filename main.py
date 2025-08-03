import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types.error_event import ErrorEvent

from app.core.config import settings
from app.db.session import create_db_and_tables, get_session
from app.handlers import agent_handlers, user_handlers
from app.middlewares.db_middleware import DbSessionMiddleware
from app.services.agent_service import sync_agents_from_env


def on_startup():
    """Выполняется при старте бота."""
    logging.info("Initializing database and tables...")
    create_db_and_tables()
    logging.info("Database initialized successfully.")

    # Синхронизация агентов при старте
    with next(get_session()) as session:
        sync_agents_from_env(session)


async def error_handler(event: ErrorEvent, bot: Bot):
    """
    Глобальный обработчик ошибок.
    Ловит все исключения, которые не были обработаны в хэндлерах.
    """
    logging.error(f"Unhandled exception: {event.exception}", exc_info=True)

    # Отправляем сообщение пользователю, если это возможно
    if event.update.message:
        user_id = event.update.message.from_user.id
        try:
            await bot.send_message(
                user_id,
                "Произошла непредвиденная ошибка. Мы уже работаем над решением. "
                "Пожалуйста, попробуйте позже.",
            )
        except Exception as e:
            logging.error(f"Failed to send error message to user {user_id}: {e}")


async def main() -> None:
    """Главная функция для запуска бота."""
    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.update.middleware(DbSessionMiddleware())

    # ПРАВИЛЬНЫЙ СПОСОБ РЕГИСТРАЦИИ:
    # Используем lambda, чтобы передать объект bot в on_startup.
    dp.startup.register(on_startup)
    # Просто регистрируем хэндлер, aiogram сам внедрит зависимость bot.
    dp.errors.register(error_handler)

    dp.include_router(user_handlers.router)
    dp.include_router(agent_handlers.router)

    logging.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
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
