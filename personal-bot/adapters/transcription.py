"""
Адаптер распознавания речи (голос → текст).

Единственное место в проекте, которое знает про OpenAI Whisper.
Если решим сменить сервис распознавания — меняется только этот файл,
остальной код продолжает вызывать transcribe(path) как раньше.
"""

from openai import OpenAI

from config import OPENAI_API_KEY

_client = OpenAI(api_key=OPENAI_API_KEY)


def transcribe(audio_file_path: str) -> str:
    """Принимает путь к аудио-файлу (.ogg из Telegram), возвращает распознанный текст."""
    with open(audio_file_path, "rb") as audio_file:
        result = _client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ru",
        )
    return result.text
