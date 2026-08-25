"""
Точка входа. Запускает Telegram-бота и подключает обработчики сообщений.

Запуск: python main.py
(сначала нужно создать .env по образцу .env.example и поставить зависимости
из requirements.txt — см. README.md)
"""

import functools
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ALLOWED_CHAT_ID, TELEGRAM_BOT_TOKEN
from handlers.dispatch import handle_choice_button
from handlers.text import handle_text_message
from handlers.voice import handle_voice

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def owner_only(handler):
    """Оборачивает любой обработчик так, чтобы он реагировал только на владельца бота."""

    @functools.wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat.id != ALLOWED_CHAT_ID:
            logger.warning(
                "Игнорирую сообщение от постороннего chat_id=%s", update.effective_chat.id
            )
            return
        await handler(update, context)

    return wrapped


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE, owner_only(handle_voice)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, owner_only(handle_text_message)))
    app.add_handler(CallbackQueryHandler(owner_only(handle_choice_button), pattern=r"^choice:"))

    logger.info("Бот запущен, жду сообщений...")
    app.run_polling()


if __name__ == "__main__":
    main()
