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

# С 2026-09-03 бот живёт не в личном чате, а в группе-форуме (Telegram
# Forum Topics) — ALLOWED_CHAT_ID теперь id этой группы, не личного чата с
# пользователем (Forum Topics физически не существуют в личных чатах).
# Каждый обработчик должен явно указывать reply в нужную тему через
# message_thread_id — без этого сообщение уйдёт в General (тема "Общие"),
# созданную Telegram автоматически при включении режима форума.
#
# id тем — постоянные (созданы один раз через createForumTopic, см. историю
# сессии 2026-09-03), не меняются при переименовании темы в интерфейсе.
TOPIC_MAIL = 4
TOPIC_TASKS = 5
TOPIC_AUTOEXPERT = 6
TOPIC_MOTUS = 7
TOPIC_FINANCE = 8

# classifier.py's message "type" → тема, куда бот должен положить ОТВЕТ —
# независимо от того, в какой теме пользователь написал исходное сообщение
# (пользователь может написать мысль хоть в "Почте", она всё равно должна
# попасть в "Задачи"). См. handlers/dispatch.py._topic_for.
#
# "thought" сюда НЕ входит намеренно — для мыслей тема зависит не только от
# типа, а ещё и от classifier.py's поля "project" (autoexpert/motus/none),
# см. TOPIC_BY_PROJECT ниже и _topic_for в dispatch.py.
TOPIC_BY_MESSAGE_TYPE = {
    "mail": TOPIC_MAIL,
    "event": TOPIC_TASKS,
    "cancel_event": TOPIC_TASKS,
    "reschedule_event": TOPIC_TASKS,
    "parts_search": TOPIC_TASKS,
    "balance": TOPIC_FINANCE,
}

# classifier.py's поле "project" (только для типа "thought") → тема. "none"
# сюда не входит — такие мысли уходят в TOPIC_TASKS по умолчанию, см.
# handlers/dispatch.py._topic_for.
TOPIC_BY_PROJECT = {
    "autoexpert": TOPIC_AUTOEXPERT,
    "motus": TOPIC_MOTUS,
}

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
