"""
Простое хранилище "какие письма уже показали" — чтобы фоновая проверка почты
не присылала одно и то же письмо повторно на каждом следующем прогоне.

Один JSON-файл со списком id прочитанных-и-показанных писем. Этого достаточно
для одного личного бота с одним пользователем — не понадобилась настоящая
база данных. Файл лежит рядом с другими локальными файлами состояния
(токенами), в .gitignore, не в git.
"""

import json
import os

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "seen_mail_ids.json")

# Ограничение размера — файл не должен расти бесконечно годами. Урезаем до
# последних N id, когда список превышает потолок; урезание не может случайно
# выбросить id, о котором мы вот-вот забудем спросить (см. save ниже).
_MAX_STORED_IDS = 2000


def _load() -> set[str]:
    if not os.path.exists(_STORE_PATH):
        return set()
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def _save(ids: set[str]) -> None:
    trimmed = list(ids)[-_MAX_STORED_IDS:]
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f)


def filter_unseen(message_ids: list[str]) -> list[str]:
    """Возвращает те id из списка, которых ещё не было среди показанных."""
    seen = _load()
    return [mid for mid in message_ids if mid not in seen]


def mark_seen(message_ids: list[str]) -> None:
    """Отмечает id как показанные — чтобы больше не всплывали в алертах."""
    if not message_ids:
        return
    seen = _load()
    seen.update(message_ids)
    _save(seen)
