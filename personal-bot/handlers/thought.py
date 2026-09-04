"""
Обработка сообщения типа "thought" — мысль/заметка на будущее.

Два режима (см. classifier.py, поле is_explicit_save):
- обычная мысль → в черновой инбокс, разберём в следующей сессии Claude Code;
- явная просьба "запомни это"/"запиши в память" → сразу полноценная
  memory-запись, видна без ожидания сессии.
"""

from adapters.memory_client import save_explicit_memory, save_thought


def handle_thought(summary: str, is_explicit_save: bool) -> tuple[str, str | None]:
    """Возвращает (текст ответа, entry_id). entry_id не None только для
    обычной мысли (черновой инбокс) — она получает кнопку "Закрыто" в
    handlers/dispatch.py, потому что это единственный путь, который
    поддерживает пометку "выполнено" (см. adapters/memory_client.py). Для
    is_explicit_save entry_id всегда None — такая запись сразу уходит в
    постоянную память отдельным файлом, вне системы задач/статусов."""
    if is_explicit_save:
        slug = save_explicit_memory(summary)
        return f"🧠 Запомнил насовсем: «{summary}».\nЗапись: {slug}", None

    entry_id = save_thought(summary)
    return (
        f"💡 Записал мысль на заметку: «{summary}».\nРазберу подробнее в следующей сессии.",
        entry_id,
    )
