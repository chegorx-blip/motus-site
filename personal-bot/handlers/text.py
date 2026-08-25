"""
Обработчик обычных текстовых сообщений (не голосовых) — используется в основном
для быстрых ответов на уточняющие вопросы бота ("1", "второй"), но также
может обрабатывать любой текст как обычную команду, как и голос.
"""

from telegram import Update
from telegram.ext import ContextTypes

from handlers.dispatch import handle_text as dispatch_text


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await dispatch_text(update, context, update.message.text)
