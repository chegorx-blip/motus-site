"""
Обработка сообщения типа "event" — от классификации до реального создания
события в Google Calendar.

Перед созданием проверяет две вещи, чтобы не плодить путаницу в расписании:
1. Наложение по времени — если на это же время уже есть другое событие,
   бот всё равно создаёт новое (пользователь может специально хотеть два
   параллельных дела), но явно предупреждает об этом в ответе.
2. Похожее название на предстоящее событие — вероятная попытка перенести
   существующую встречу, а не завести новую (см. диагностированный случай:
   "перенеси встречу на три" был распознан как "event" и создал дубликат
   вместо переноса). В этом случае бот СПРАШИВАЕТ, не переносит ли
   пользователь то же самое событие, вместо того чтобы молча создавать копию.
"""

import datetime

from adapters.calendar_client import create_event, find_overlapping_events, find_upcoming_events
from date_parser import resolve

PENDING_KEY = "pending_event_duplicate_check"


def _format_overlap_warning(overlaps: list[dict]) -> str:
    if not overlaps:
        return ""
    listing = "\n".join(f"— «{o['summary']}» ({o['start']})" for o in overlaps)
    return f"\n\n⚠️ Обрати внимание, на это же время уже есть:\n{listing}"


def handle_event(title: str, date_hint: str, user_data: dict) -> tuple[str, list[dict] | None]:
    """
    Вычисляет точное время из date_hint. Если находит предстоящее событие с
    очень похожим названием — не создаёт сразу, а спрашивает (кандидаты
    возвращаются voice.py для показа кнопок "да, новое" / номер существующего).
    Возвращает (текст_ответа, кандидаты_на_уточнение_или_None).
    """
    resolved = resolve(date_hint)
    start = datetime.datetime.strptime(
        f"{resolved['date']} {resolved['time']}", "%Y-%m-%d %H:%M"
    )
    reminders = resolved.get("reminders_minutes_before") or [60]

    similar, _is_uncertain = find_upcoming_events(title)
    if similar:
        user_data[PENDING_KEY] = {
            "title": title,
            "start": start.isoformat(),
            "reminders": reminders,
            "similar": similar,
        }
        listing = "\n".join(f"— «{m['summary']}» ({m['start']})" for m in similar)
        return (
            f"🤔 Нашёл похожее предстоящее событие:\n{listing}\n\n"
            f"Это перенос одного из них на {start.strftime('%d.%m.%Y в %H:%M')}, "
            f"или отдельное новое событие «{title}»? Ответь «новое» или номером "
            f"события, которое имелось в виду.",
            similar,
        )

    return _create_now(title, start, reminders), None


def resolve_pending_duplicate_check(user_data: dict, wants_new: bool) -> str:
    """
    Вызывается после ответа пользователя на вопрос "новое или перенос":
    wants_new=True — создаёт как отдельное новое событие несмотря на сходство.
    (Выбор конкретного существующего события для переноса вместо этого
    обрабатывается через handlers/reschedule_event.py — пользователь в этом
    случае просто озвучивает перенос заново, здесь только ветка "да, новое".)
    """
    pending = user_data.pop(PENDING_KEY, None)
    if not pending:
        return "🤔 Этот вопрос уже неактуален — попробуй сказать заново."
    if not wants_new:
        return (
            "Хорошо, тогда скажи «перенеси [событие] на [время]» — это отдельная "
            "команда, которая изменит время существующего события, не создаст новое."
        )

    start = datetime.datetime.fromisoformat(pending["start"])
    return _create_now(pending["title"], start, pending["reminders"])


def _create_now(title: str, start: datetime.datetime, reminders: list[int]) -> str:
    overlaps = find_overlapping_events(start, start + datetime.timedelta(minutes=1))
    link = create_event(title=title, start=start, reminders_minutes_before=reminders)

    reminders_text = " и ".join(_format_reminder(m) for m in reminders)
    warning = _format_overlap_warning(overlaps)
    return (
        f"📅 Запланировал: «{title}» на {start.strftime('%d.%m.%Y в %H:%M')}.\n"
        f"Напомню за {reminders_text}.\n{link}{warning}"
    )


def _format_reminder(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} ч" if hours != 1 else "час"
    return f"{minutes} мин"
