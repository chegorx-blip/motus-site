"""
Обработка сообщения типа "cancel_event" — найти подходящее предстоящее
событие по ключевым словам и удалить его.

Намеренно НЕ угадывает при неоднозначности: если найдено больше одного
похожего события, или ничего не найдено, или пользователь не назвал ничего
конкретного — бот честно об этом говорит, а не удаляет наугад. Ошибочно
удалённое событие не так просто исправить, как заново сказать более точно.

Когда вариантов несколько, бот присылает кнопки с номерами (см. voice.py —
там же собирается клавиатура) и запоминает список кандидатов в user_data,
чтобы понять, к чему относится нажатие кнопки ИЛИ следующее голосовое "1"/"второй".
"""

from adapters.calendar_client import delete_event, find_upcoming_events

PENDING_KEY = "pending_cancel_candidates"


def handle_cancel_event(search_query: str, user_data: dict) -> tuple[str, list[dict] | None]:
    """
    Возвращает (текст_ответа, кандидаты_или_None).
    Если кандидаты не None — voice.py должен показать кнопки выбора.
    """
    if not search_query:
        return (
            "🤔 Не понял, какое именно событие отменить — скажи, например, "
            "«отмени встречу с врачом».",
            None,
        )

    matches = find_upcoming_events(search_query)

    if not matches:
        return f"🤔 Не нашёл предстоящих событий, похожих на «{search_query}».", None

    if len(matches) > 1:
        user_data[PENDING_KEY] = matches
        listing = "\n".join(
            f"{i + 1}. {m['summary']} ({m['start']})" for i, m in enumerate(matches)
        )
        return (
            f"🤔 Нашёл несколько подходящих событий, выбери какое (кнопкой или голосом номер):\n{listing}",
            matches,
        )

    event = matches[0]
    delete_event(event["id"])
    return f"🗑️ Отменил: «{event['summary']}» ({event['start']}).", None


def resolve_pending_choice(user_data: dict, choice_index: int) -> str:
    """Вызывается, когда пользователь выбрал номер (кнопкой или голосом) из списка кандидатов."""
    matches = user_data.pop(PENDING_KEY, None)
    if not matches or not (0 <= choice_index < len(matches)):
        return "🤔 Этот выбор уже неактуален — попробуй назвать событие заново."

    event = matches[choice_index]
    delete_event(event["id"])
    return f"🗑️ Отменил: «{event['summary']}» ({event['start']})."
