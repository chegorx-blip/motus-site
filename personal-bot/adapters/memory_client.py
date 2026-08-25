"""
Адаптер работы с памятью Claude Code.

Единственное место в проекте, которое знает про файловую структуру памяти
(папка CLAUDE_MEMORY_DIR — на самом деле junction/symlink на Google Drive,
поэтому запись сюда синхронизируется на Windows и Mac сама собой).

Два разных пути записи мысли, в зависимости от того, попросил ли пользователь
явно "запомнить" (см. classifier.py, поле is_explicit_save):

- save_thought() — обычная мысль без явной просьбы. Дописывается строкой в
  общий черновой файл memory_inbox.md. Ничего не удаляет и не решает за
  пользователя, куда мысль относится — это остаётся на разбор в следующей
  сессии Claude Code (как обычные задачи/заметки).
- save_explicit_memory() — пользователь прямо сказал "запомни"/"запиши в
  память". Создаёт полноценный memory-файл с frontmatter (тот же формат,
  что использует сам Claude Code) и добавляет строку-указатель в MEMORY.md,
  чтобы запись была видна сразу, без ожидания следующей сессии.
"""

import datetime
import re
from pathlib import Path

from config import CLAUDE_MEMORY_DIR

_INBOX_FILENAME = "memory_inbox.md"
_INDEX_FILENAME = "MEMORY.md"


def _memory_dir() -> Path:
    path = Path(CLAUDE_MEMORY_DIR)
    if not path.is_dir():
        raise RuntimeError(
            f"Папка памяти не найдена: {CLAUDE_MEMORY_DIR}. "
            f"Проверь CLAUDE_MEMORY_DIR в .env и что junction/symlink на месте."
        )
    return path


def save_thought(summary: str) -> None:
    """Дописывает мысль строкой в черновой инбокс — без создания memory-файла."""
    inbox_path = _memory_dir() / _INBOX_FILENAME
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"## {timestamp}\n{summary.strip()}\n\n"
    with inbox_path.open("a", encoding="utf-8") as f:
        f.write(entry)


def _slugify(summary: str) -> str:
    """Грубый slug для имени файла из текста мысли: латиница/цифры/дефисы,
    ограничен по длине, всегда с префиксом даты, чтобы разные мысли с похожим
    текстом не перезаписали друг друга."""
    date_prefix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ascii_only = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")
    short = "-".join(ascii_only.split("-")[:6]) or "note"
    return f"inbox_{date_prefix}_{short}"[:80]


def save_explicit_memory(summary: str) -> str:
    """
    Пользователь явно попросил запомнить — создаёт полноценный memory-файл
    с frontmatter и добавляет строку в MEMORY.md. Тип всегда "project" —
    самый безопасный дефолт для мысли с телефона без дополнительного контекста;
    при следующем разборе в сессии Claude может переклассифицировать при
    необходимости.

    Возвращает slug созданной записи (для ответа пользователю).
    """
    memory_dir = _memory_dir()
    slug = _slugify(summary)
    file_path = memory_dir / f"{slug}.md"

    content = (
        "---\n"
        f"name: {slug}\n"
        f"description: {summary.strip()[:200]}\n"
        "metadata:\n"
        "  type: project\n"
        "---\n\n"
        f"{summary.strip()}\n\n"
        "**Why:** записано с телефона через Telegram-бот по явной просьбе "
        "«запомни» — контекст не уточнялся, при случае стоит дополнить.\n"
    )
    file_path.write_text(content, encoding="utf-8")

    index_path = memory_dir / _INDEX_FILENAME
    short_hook = summary.strip().split("\n")[0][:100]
    index_line = f"- [{slug}]({file_path.name}) — {short_hook}\n"
    with index_path.open("a", encoding="utf-8") as f:
        f.write(index_line)

    return slug
