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

# Название Gmail-метки для срочной почты (банки, оплаты, авиабилеты, дедлайны)
# — пользователь сам заводит фильтр/метку с этим именем в Gmail, бот только
# проверяет, есть ли под ней новые непрочитанные письма. Не обязательный
# .env-параметр (есть разумное значение по умолчанию) — но можно переопределить,
# если решишь назвать метку иначе, не трогая код.
URGENT_LABEL_NAME = os.getenv("URGENT_LABEL_NAME", "Urgent")
