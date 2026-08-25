"""
Обработка сообщения типа "thought" — мысль/заметка на будущее.

Два режима (см. classifier.py, поле is_explicit_save):
- обычная мысль → в черновой инбокс, разберём в следующей сессии Claude Code;
- явная просьба "запомни это"/"запиши в память" → сразу полноценная
  memory-запись, видна без ожидания сессии.
"""

from adapters.memory_client import save_explicit_memory, save_thought


def handle_thought(summary: str, is_explicit_save: bool) -> str:
    if is_explicit_save:
        slug = save_explicit_memory(summary)
        return f"🧠 Запомнил насовсем: «{summary}».\nЗапись: {slug}"

    save_thought(summary)
    return f"💡 Записал мысль на заметку: «{summary}».\nРазберу подробнее в следующей сессии."
