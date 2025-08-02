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
from app.services.agent_service import sync_agents_from_env


def on_startup(bot: Bot):
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
    # event.update содержит объект Update, из которого можно извлечь пользователя
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
    # Инициализация бота
    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Инициализация диспетчера
    dp = Dispatcher()

    # Регистрация событий жизненного цикла
    dp.startup.register(on_startup)

    # Регистрация хэндлеров и роутеров
    dp.include_router(user_handlers.router)
    dp.include_router(agent_handlers.router)

    # Регистрация глобального обработчика ошибок
    dp.errors.register(error_handler, bot=bot)

    logging.info("Starting bot...")
    # Удаляем вебхук и запускаем long polling
    await bot.delete_webhook(drop_pending_updates=True)
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
