"""
Читает настройки из .env и один раз проверяет, что все ключи на месте.
Если что-то забыто — бот сразу же скажет об этом понятным текстом,
вместо непонятной ошибки где-то в середине работы.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Не заполнена настройка {name} в файле .env. "
            f"Скопируй .env.example в .env и впиши туда значение."
        )
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = _require("OPENAI_API_KEY")
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
ALLOWED_CHAT_ID = int(_require("ALLOWED_CHAT_ID"))
CLAUDE_MEMORY_DIR = _require("CLAUDE_MEMORY_DIR")

# 4 почтовых ящика, которые бот проверяет на срочные письма — mailbox_id
# (короткий технический ярлык, используется в именах токен-файлов и в
# правилах срочности) сопоставлен с реальным адресом (только для читаемости
# в сообщениях бота, в Gmail API не используется — авторизация идёт через
# отдельный OAuth-токен на каждый ящик, см. adapters/gmail_client.py).
# Те же 4 адреса, что уже подключены через workspace-mcp на этой машине
# (см. память Claude Code, goal_multi_gmail_connector) — тут отдельная,
# независимая авторизация именно для personal-bot.
MAILBOXES = {
    "chegorx": "chegorx@gmail.com",
    "motus_cy": "motus.cy@gmail.com",
    "autoexpertt21": "autoexpertt21@gmail.com",
    "autoexpert_cy": "autoexpert.cy@gmail.com",
}
