"""
Классификатор срочности одного письма — отдельный от classifier.py (тот
разбирает голосовые команды пользователя, этот разбирает чужие входящие
письма — разные задачи, разные system prompt'ы).

Судит по общим признакам (банки, оплаты, авиабилеты, дедлайны, поставщики с
просьбами) + по накопленным примерам прошлых оценок пользователя (см.
adapters/urgency_rules.py) — так классификатор со временем подстраивается под
конкретные привычки пользователя без переписывания кода, только за счёт
нажатий ✅/❌ под алертами.

Использует user_context (профиль владельца) — это как раз тот случай
"content-generating функции", для которого user_context.py и был задуман
(см. его docstring): понимание срочности требует знать, кто пользователь и
чем занимается (AutoExpert, Motus), не только текст письма.
"""

from adapters.claude_client import ask_structured
from adapters.mail_translator import strip_invisible
from adapters.urgency_rules import format_rules_for_prompt
from user_context import get_user_context

_SYSTEM_PROMPT = """\
Ты помогаешь личному помощнику решить, достойно ли входящее письмо push-уведомления \
прямо сейчас, или может подождать до дневной сводки.

СРОЧНО — письма, которые касаются денег/сроков и требуют быстрой реакции: \
банки, оплаты, счета, авиабилеты и другие вещи с датой/дедлайном, поставщики с \
просьбой о решении. Не срочно — рассылки, уведомления соцсетей, реклама, письма \
без действия от пользователя, обычная переписка без срока.

{user_context}
{rules}

Дополнительно переведи тему и фрагмент письма на русский (subject_ru/snippet_ru) \
— коротко, по сути. Имена собственные (бренды, компании, географические названия, \
имена людей) НЕ переводи, оставляй как есть. Если уже на русском — верни как есть.

Ответь про ОДНО присланное письмо (тема, отправитель, короткий фрагмент текста)."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "urgent": {"type": "boolean"},
        "reason": {"type": "string"},
        "subject_ru": {"type": "string"},
        "snippet_ru": {"type": "string"},
    },
    "required": ["urgent", "reason", "subject_ru", "snippet_ru"],
    "additionalProperties": False,
}


def classify_urgency(sender: str, subject: str, snippet: str) -> dict:
    """Возвращает {"urgent": bool, "reason": "...", "subject_ru": "...",
    "snippet_ru": "..."} для одного письма. Перевод (subject_ru/snippet_ru)
    достаётся "бесплатно" в этом же вызове — отдельного вызова только на
    перевод для срочных писем не нужно (в отличие от дневной сводки/поиска,
    у которых нет своего LLM-вызова — см. adapters/mail_translator.py)."""
    system_prompt = _SYSTEM_PROMPT.format(
        user_context=get_user_context(), rules=format_rules_for_prompt()
    )
    # Тот же Unicode-мусор рассылок, что сбивал перевод в mail_translator.py,
    # мог точно так же засорять и этот вызов — чистим на входе (см. strip_invisible).
    clean_subject = strip_invisible(subject)
    clean_snippet = strip_invisible(snippet)
    user_message = f"От: {sender}\nТема: {clean_subject}\nФрагмент: {clean_snippet}"
    return ask_structured(system_prompt, user_message, _SCHEMA)
