"""
Хранилище правил "что срочно" — живой список примеров, который растёт по мере
того, как пользователь жмёт ✅/❌ под алертами (см. handlers/mail_alerts.py).

Каждое правило — одна прошлая оценка пользователя, привязанная к отправителю
и теме конкретного письма: {"sender": "...", "subject": "...", "urgent": bool}.
Никакой отдельной "модели" не обучаем — вместо этого весь список примеров
целиком уходит в system prompt urgency_classifier.py, и Claude сам решает по
образцу, попадает ли новое письмо в ту же картину. Просто, прозрачно, легко
почистить руками (обычный JSON-файл), не требует переобучения.

Один JSON-файл, общий на все 4 почтовых ящика (см. решение пользователя —
общие правила срочности для старта, не разделять по ящику).
"""

import json
import os

_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "urgency_rules.json")

# Потолок на количество хранимых правил — так же, как в seen_store.py: не
# даём файлу расти бесконечно, и не даём system prompt классификатора
# распухать (каждое правило — это токены на каждый вызов). Свежие правила
# важнее старых, поэтому при переполнении обрезаем с начала списка.
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


def add_rule(sender: str, subject: str, urgent: bool) -> None:
    """Запоминает одну оценку пользователя (нажатие ✅/❌ под алертом)."""
    rules = _load()
    rules.append({"sender": sender, "subject": subject, "urgent": urgent})
    _save(rules)


def get_rules() -> list[dict]:
    return _load()


def format_rules_for_prompt() -> str:
    """Правила в виде текстового блока для system prompt классификатора.
    Пустая строка, если правил ещё нет — тогда классификатор судит только по
    общим инструкциям, без примеров с телефона пользователя."""
    rules = _load()
    if not rules:
        return ""

    lines = []
    for rule in rules:
        verdict = "СРОЧНО" if rule["urgent"] else "не срочно"
        lines.append(f'- От "{rule["sender"]}", тема "{rule["subject"]}" → {verdict}')
    return (
        "\nПРИМЕРЫ ИЗ ПРОШЛЫХ ОЦЕНОК ПОЛЬЗОВАТЕЛЯ (учитывай похожие письма так же):\n"
        + "\n".join(lines)
    )
