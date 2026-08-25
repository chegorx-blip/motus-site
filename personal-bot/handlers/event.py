"""
Обработка сообщения типа "event" — от классификации до реального создания
события в Google Calendar.
"""

import datetime

from adapters.calendar_client import create_event
from date_parser import resolve


def handle_event(title: str, date_hint: str) -> str:
    """
    Вычисляет точное время из date_hint, создаёт событие в календаре,
    возвращает текст ответа пользователю (человеческое подтверждение + ссылка).
    """
    resolved = resolve(date_hint)
    start = datetime.datetime.strptime(
        f"{resolved['date']} {resolved['time']}", "%Y-%m-%d %H:%M"
    )
    reminders = resolved.get("reminders_minutes_before") or [60]

    link = create_event(
        title=title,
        start=start,
        reminders_minutes_before=reminders,
    )

    reminders_text = " и ".join(_format_reminder(m) for m in reminders)
    return (
        f"📅 Запланировал: «{title}» на {start.strftime('%d.%m.%Y в %H:%M')}.\n"
        f"Напомню за {reminders_text}.\n{link}"
    )


def _format_reminder(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} ч" if hours != 1 else "час"
    return f"{minutes} мин"
