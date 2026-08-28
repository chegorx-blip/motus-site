"""
Перевод темы+фрагмента писем на русский — для мест, где своего LLM-вызова
ещё нет (дневная сводка, поиск по запросу). Срочные алерты переводятся иначе,
без этого файла — см. adapters/urgency_classifier.py, где перевод получаем
"бесплатно" в том же вызове, что уже классифицирует срочность.

Один вызов Claude на ВСЮ пачку писем сразу (не по одному) — иначе дневная
сводка из 10 писем стоила бы 10 отдельных вызовов только на перевод.
"""

import re

from adapters.claude_client import ask_structured

# Письма-рассылки часто набивают тему/сниппет невидимыми Unicode-символами
# (трекинг-мусор рассылочных сервисов, не текст) — сотни таких символов в
# одном коротком сниппете сбивали перевод (живой тест 2026-08-27: письмо с
# этим мусором осталось непереведённым, то же письмо без мусора переводилось
# нормально). Чистим перед отправкой в LLM, а не пытаемся промптом объяснять
# модели их игнорировать. Коды заданы через \uXXXX, а не сами символы — они
# невидимы и нечитаемы в исходном файле.
_INVISIBLE_CODEPOINTS = (
    "​-‏"  # zero-width space/joiner/non-joiner, LTR/RTL marks
    "﻿"  # BOM / zero-width no-break space
    "⠀"  # Braille pattern blank (newsletters use it as invisible spacer)
    "͏"  # combining grapheme joiner
    "᠎"  # Mongolian vowel separator
    "⁠-⁤"  # word joiner and invisible math operators
)
_INVISIBLE_CHARS_RE = re.compile(f"[{_INVISIBLE_CODEPOINTS}]+")


def strip_invisible(text: str) -> str:
    """Убирает Unicode-мусор рассылок из текста. Публичная — переиспользуется
    в adapters/urgency_classifier.py, у которого тот же источник грязных
    сниппетов, но свой отдельный LLM-вызов (не через translate_mails)."""
    return _INVISIBLE_CHARS_RE.sub(" ", text).strip()


_SYSTEM_PROMPT = """\
Переведи тему и фрагмент каждого письма на русский язык — коротко, по сути,
сохраняя смысл. Имена собственные (бренды, названия компаний, географические \
названия, имена людей) НЕ переводи, оставляй как есть — это идентификаторы, \
не текст для перевода. Если тема/фрагмент уже на русском — верни как есть.

Верни перевод для КАЖДОГО письма в том же порядке, в котором они присланы."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject_ru": {"type": "string"},
                    "snippet_ru": {"type": "string"},
                },
                "required": ["subject_ru", "snippet_ru"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["translations"],
    "additionalProperties": False,
}


def translate_mails(mails: list[dict]) -> list[dict]:
    """Возвращает НОВЫЙ список карточек писем (не мутирует вход) с добавленными
    subject_ru/snippet_ru. Если перевод не удался (сеть/API) — возвращает
    карточки как есть, с subject_ru/snippet_ru равными оригиналу, чтобы вызов
    никогда не ронял сводку целиком из-за сбоя перевода."""
    if not mails:
        return []

    cleaned = [
        {"subject": strip_invisible(m["subject"]), "snippet": strip_invisible(m["snippet"])}
        for m in mails
    ]
    user_message = "\n\n".join(
        f"{i + 1}. Тема: {m['subject']}\nФрагмент: {m['snippet']}" for i, m in enumerate(cleaned)
    )
    try:
        result = ask_structured(_SYSTEM_PROMPT, user_message, _SCHEMA)
        translations = result.get("translations", [])
    except Exception:
        translations = []

    translated = []
    for i, mail in enumerate(mails):
        item = dict(mail)
        if i < len(translations):
            item["subject_ru"] = translations[i].get("subject_ru") or mail["subject"]
            item["snippet_ru"] = translations[i].get("snippet_ru") or mail["snippet"]
        else:
            item["subject_ru"] = mail["subject"]
            item["snippet_ru"] = mail["snippet"]
        translated.append(item)
    return translated
