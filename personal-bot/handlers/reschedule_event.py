"""
Обработка сообщения типа "reschedule_event" — найти существующее событие по
ключевым словам и перенести его на новое время (не удалять и не создавать
заново — см. adapters/calendar_client.reschedule_event).

Логика поиска кандидатов зеркалит handlers/cancel_event.py (тот же честный
подход: не угадывать при неоднозначности), только вместо удаления в конце —
перенос. Использует отдельный PENDING_KEY, чтобы не путать с "какое событие
отменить", если оба ожидания почему-то пересекутся.
"""

import datetime

from adapters.calendar_client import find_overlapping_events, find_upcoming_events
from adapters.calendar_client import reschedule_event as _reschedule_event_api
from date_parser import resolve

PENDING_KEY = "pending_reschedule_candidates"
_PENDING_NEW_START_KEY = "pending_reschedule_new_start"


def _format_overlap_warning(overlaps: list[dict], exclude_id: str) -> str:
    others = [o for o in overlaps if o["id"] != exclude_id]
    if not others:
        return ""
    listing = "\n".join(f"— «{o['summary']}» ({o['start']})" for o in others)
    return f"\n\n⚠️ Обрати внимание, на это же время уже есть:\n{listing}"


def handle_reschedule_event(
    search_query: str, date_hint: str, user_data: dict
) -> tuple[str, list[dict] | None]:
    """
    Возвращает (текст_ответа, кандидаты_или_None) — как handle_cancel_event.
    Если кандидатов несколько, voice.py показывает кнопки выбора; после выбора
    вызывается resolve_pending_choice ниже.
    """
    if not search_query:
        return (
            "🤔 Не понял, какое именно событие перенести — скажи, например, "
            "«перенеси встречу с врачом на завтра».",
            None,
        )
    if not date_hint:
        return (
            "🤔 Понял, какое событие, но не понял, на какое время его перенести.",
            None,
        )

    matches, is_uncertain = find_upcoming_events(search_query)
    if not matches:
        return f"🤔 Не нашёл предстоящих событий, похожих на «{search_query}».", None

    resolved = resolve(date_hint)
    new_start = datetime.datetime.strptime(
        f"{resolved['date']} {resolved['time']}", "%Y-%m-%d %H:%M"
    )

    if len(matches) > 1 or is_uncertain:
        user_data[PENDING_KEY] = matches
        user_data[_PENDING_NEW_START_KEY] = new_start.isoformat()
        listing = "\n".join(
            f"{i + 1}. {m['summary']} ({m['start']})" for i, m in enumerate(matches)
        )
        question = (
            "Нашёл вот это, но не уверен, что то самое — точно его переносим?"
            if is_uncertain and len(matches) == 1
            else "Нашёл несколько подходящих событий, выбери какое перенести"
        )
        return (
            f"🤔 {question} (кнопкой или голосом номер):\n{listing}",
            matches,
        )

    return _do_reschedule(matches[0], new_start), None


def resolve_pending_choice(user_data: dict, choice_index: int) -> str:
    """Вызывается, когда пользователь выбрал номер из списка кандидатов на перенос."""
    matches = user_data.pop(PENDING_KEY, None)
    new_start_iso = user_data.pop(_PENDING_NEW_START_KEY, None)
    if not matches or not new_start_iso or not (0 <= choice_index < len(matches)):
        return "🤔 Этот выбор уже неактуален — попробуй назвать событие заново."

    new_start = datetime.datetime.fromisoformat(new_start_iso)
    return _do_reschedule(matches[choice_index], new_start)


def _do_reschedule(event: dict, new_start: datetime.datetime) -> str:
    # длительность события пока неизвестна здесь — reschedule_event сам
    # сохраняет исходную длительность, поэтому конец диапазона для проверки
    # наложений берём с запасом в 1 минуту (точная проверка внутри adapter'а
    # не нужна — здесь только предупредить пользователя, не заблокировать)
    overlaps = find_overlapping_events(new_start, new_start + datetime.timedelta(minutes=1))
    link = _reschedule_event_api(event["id"], new_start)
    warning = _format_overlap_warning(overlaps, exclude_id=event["id"])
    return (
        f"🔄 Перенёс: «{event['summary']}» на {new_start.strftime('%d.%m.%Y в %H:%M')}.\n"
        f"{link}{warning}"
    )
