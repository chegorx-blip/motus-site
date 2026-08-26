"""
Точка входа. Запускает Telegram-бота, подключает обработчики сообщений и
фоновые проверки почты (см. handlers/mail_alerts.py).

Запуск: python main.py
(сначала нужно создать .env по образцу .env.example и поставить зависимости
из requirements.txt — см. README.md)

Важно: фоновые проверки работают только пока сам процесс запущен (см.
README.md, раздел "постоянный хостинг 24/7" — пока не сделан). Планировщик —
встроенный JobQueue из python-telegram-bot, отдельная библиотека не нужна.
"""

import datetime
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
from handlers.mail_alerts import check_urgent_mail, send_daily_mail_summary
from handlers.text import handle_text_message
from handlers.voice import handle_voice

# Задача тикает круглосуточно каждые 30 минут; окно 07:30–22:30, вне которого
# она ничего не делает, проверяется внутри check_urgent_mail самой (см.
# handlers/mail_alerts.py) — так тот файл остаётся самодостаточным.
_URGENT_CHECK_INTERVAL_SECONDS = 30 * 60
_DAILY_SUMMARY_TIME = datetime.time(hour=8, minute=0)

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

    # JobQueue требует, чтобы python-telegram-bot был установлен с extra
    # "job-queue" (см. requirements.txt) — без этого app.job_queue будет None.
    app.job_queue.run_repeating(check_urgent_mail, interval=_URGENT_CHECK_INTERVAL_SECONDS, first=10)
    app.job_queue.run_daily(send_daily_mail_summary, time=_DAILY_SUMMARY_TIME)

    logger.info("Бот запущен, жду сообщений...")
    app.run_polling()


if __name__ == "__main__":
    main()
