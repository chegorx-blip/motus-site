"""
Превращает человеческое описание даты/времени ("в понедельник в 9 утра",
"завтра вечером", "через час") в точный момент времени, понятный календарю.

Почему это отдельный шаг, а не часть classifier.py: там Claude просто
фиксирует, что сказал пользователь, здесь — конкретно вычисляет дату,
зная сегодняшнее число. Раздельная ответственность, проще проверять и менять.
"""

import datetime

from adapters.claude_client import ask_structured

_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string", "description": "формат YYYY-MM-DD"},
        "time": {"type": "string", "description": "формат HH:MM, 24-часовой"},
        "reminders_minutes_before": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "за сколько минут до события напомнить; если не сказано явно — [60]",
        },
    },
    "required": ["date", "time", "reminders_minutes_before"],
    "additionalProperties": False,
}


def resolve(date_hint: str, now: datetime.datetime | None = None) -> dict:
    """
    Возвращает {"date": "2026-08-25", "time": "09:00", "reminders_minutes_before": [60]}
    на основе фразы вроде "в понедельник в 9 утра" и текущего момента времени.
    """
    now = now or datetime.datetime.now()
    system_prompt = (
        f"Сегодня {now.strftime('%Y-%m-%d')} ({now.strftime('%A')}), сейчас "
        f"{now.strftime('%H:%M')}. Пользователь описал дату/время события своими "
        f"словами. Вычисли точную дату и время. Если время не указано явно — "
        f"поставь 09:00. Если день недели упомянут без уточнения 'следующий' — "
        f"это ближайший такой день (если сегодня понедельник и сказано "
        f"'в понедельник' — подразумевается сегодня, если время ещё не прошло, "
        f"иначе — следующий понедельник). Если пользователь явно попросил "
        f"несколько напоминаний (например 'за час и за 13 часов') — верни оба "
        f"в минутах. Если не попросил — верни [60] (напомнить за час)."
    )
    return ask_structured(system_prompt, date_hint, _SCHEMA)
