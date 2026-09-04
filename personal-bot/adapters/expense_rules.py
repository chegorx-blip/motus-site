"""
Хранилище правил "какому проекту принадлежит трата" — растёт по мере того,
как пользователь поправляет категорию кнопкой под карточкой распознанного
чека (см. handlers/photo.py). Тот же приём, что adapters/urgency_rules.py
для срочности почты: никакой отдельной "модели", просто список примеров
целиком уходит в system prompt adapters/receipt_vision.py, и Claude сам
решает по образцу, к какой категории отнести новый чек с похожим сервисом.

Одно правило: {"service": "Google One", "category": "none"}.
"""

import json
import os

_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "expense_rules.json")

# Тот же потолок и та же причина, что в urgency_rules.py — не даём файлу и
# system prompt'у расти бесконечно.
_MAX_RULES = 200


def _load() -> list[dict]:
    if not os.path.exists(_RULES_PATH):
        return []
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(rules: list[dict]) -> None:
    trimmed = rules[-_MAX_RULES:]
    with open(_RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def add_rule(service: str, category: str) -> None:
    """Запоминает поправку пользователя (нажатие кнопки категории под
    карточкой распознанного чека)."""
    rules = _load()
    rules.append({"service": service, "category": category})
    _save(rules)


def format_rules_for_prompt() -> str:
    """Правила в виде текстового блока для system prompt Vision-распознавания
    чеков. Пустая строка, если правил ещё нет."""
    rules = _load()
    if not rules:
        return ""

    lines = [f'- "{rule["service"]}" → {rule["category"]}' for rule in rules]
    return (
        "\nПРИМЕРЫ ИЗ ПРОШЛЫХ ИСПРАВЛЕНИЙ ПОЛЬЗОВАТЕЛЯ (учитывай похожие сервисы так же):\n"
        + "\n".join(lines)
    )
