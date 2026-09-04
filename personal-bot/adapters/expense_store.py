"""
Хранилище распознанных трат (скриншоты чеков/подписок из темы "Финансы").

Отдельный JSON-файл (не memory_inbox.md, как для мыслей) — тратам нужны
структурированные поля (сумма, валюта, категория), по которым нужно
считать суммы за период, а не просто читать текст построчно.

Формат одной записи:
{
    "id": "20260904-162230",           # тот же формат id, что у мыслей —
                                        # YYYYMMDD-HHMMSS, для кнопки
                                        # исправления категории
    "timestamp": "2026-09-04 16:22",
    "service": "Google One",
    "amount": 4.99,
    "currency": "EUR",
    "category": "none",                # "autoexpert" / "motus" / "none" (личное)
    "is_subscription": true,
    "raw_summary": "..."               # короткое пояснение от Vision — на
                                        # случай, если сумму/сервис распознал
                                        # неточно, пользователь видит источник
}

category можно поправить кнопками после сохранения (см. handlers/photo.py) —
правки уходят в adapters/expense_rules.py, тот же паттерн, что уже работает
для срочности почты (adapters/urgency_rules.py).
"""

import datetime
import json
from pathlib import Path

from config import CLAUDE_MEMORY_DIR

_EXPENSES_FILENAME = "expenses.json"

# Потолок записей — тот же приём, что в adapters/urgency_rules.py и
# adapters/seen_store.py: не даём файлу расти бесконечно. 2000 трат — это
# годы использования при разумной частоте скриншотов.
_MAX_EXPENSES = 2000


def _expenses_path() -> Path:
    path = Path(CLAUDE_MEMORY_DIR)
    if not path.is_dir():
        raise RuntimeError(
            f"Папка памяти не найдена: {CLAUDE_MEMORY_DIR}. "
            f"Проверь CLAUDE_MEMORY_DIR в .env и что junction/symlink на месте."
        )
    return path / _EXPENSES_FILENAME


def _load() -> list[dict]:
    path = _expenses_path()
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(expenses: list[dict]) -> None:
    trimmed = expenses[-_MAX_EXPENSES:]
    _expenses_path().write_text(
        json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_expense(
    service: str,
    amount: float,
    currency: str,
    category: str,
    is_subscription: bool,
    raw_summary: str,
) -> str:
    """Сохраняет новую трату, возвращает её id (для кнопок исправления
    категории, см. handlers/photo.py)."""
    now = datetime.datetime.now()
    entry_id = now.strftime("%Y%m%d-%H%M%S")
    expenses = _load()
    expenses.append(
        {
            "id": entry_id,
            "timestamp": now.strftime("%Y-%m-%d %H:%M"),
            "service": service,
            "amount": amount,
            "currency": currency,
            "category": category,
            "is_subscription": is_subscription,
            "raw_summary": raw_summary,
        }
    )
    _save(expenses)
    return entry_id


def list_expenses(category: str | None = None) -> list[dict]:
    """Все траты, свежие последними. category=None — все категории сразу."""
    expenses = _load()
    if category is not None:
        expenses = [e for e in expenses if e["category"] == category]
    return expenses


def set_expense_category(entry_id: str, category: str) -> dict | None:
    """Меняет категорию одной траты (исправление после кнопки) и возвращает
    обновлённую запись целиком — так handlers/expenses.py может взять
    "service" из самих данных, а не парсить его обратно из текста карточки
    в Telegram (могло бы разъехаться, если бы service содержал ":" или
    другой символ форматирования). None, если записи с таким id не нашлось."""
    expenses = _load()
    for e in expenses:
        if e["id"] == entry_id:
            e["category"] = category
            _save(expenses)
            return e
    return None
