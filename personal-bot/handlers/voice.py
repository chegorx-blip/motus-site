"""
Обработчик голосовых сообщений.

Шаги: получить голосовое → распознать текст (Whisper) → отдать распознанный
текст в handlers/dispatch.py (общая логика, одинаковая для голоса и текста).
"""

import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from adapters.transcription import transcribe
from handlers.dispatch import handle_text


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    voice = update.message.voice
    telegram_file = await context.bot.get_file(voice.file_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        ogg_path = os.path.join(tmp_dir, "voice.ogg")
        await telegram_file.download_to_drive(ogg_path)

        await update.message.reply_text("🎧 Слушаю...")
        text = transcribe(ogg_path)

    await handle_text(update, context, text, prefix=f"Расслышал: «{text}»\n\n")
