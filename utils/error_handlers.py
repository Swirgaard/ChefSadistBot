import logging
from aiogram import Dispatcher
from aiogram.types import ErrorEvent

async def handle_telegram_errors(event: ErrorEvent):
    """
    Обработчик для непредвиденных ошибок Telegram API.
    """
    logging.error(f"Произошла ошибка Telegram: {event.exception}", exc_info=True)

def register_error_handlers(dp: Dispatcher):
    """Регистрирует обработчики ошибок в диспетчере."""
    dp.errors.register(handle_telegram_errors)