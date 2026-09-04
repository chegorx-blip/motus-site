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

Начиная с 2026-09-04 каждая запись в memory_inbox.md несёт свой ID в
заголовке (см. _parse_entries) — нужен, чтобы кнопка "Закрыто" под мыслью в
Telegram (см. handlers/dispatch.py) могла однозначно сослаться на ЭТУ
конкретную запись через callback_data. Записи, сохранённые до этой даты
(без ID в заголовке), read-функции ниже просто пропускают как невозможные
разобрать — они никуда не делись, лежат в файле как есть, просто не
попадают в /список открытых задач и не могут получить кнопку "Закрыто"
задним числом. Пользователь был предупреждён, это не потеря данных.
"""

import datetime
import re
from pathlib import Path

from config import CLAUDE_MEMORY_DIR

_INBOX_FILENAME = "memory_inbox.md"
_INDEX_FILENAME = "MEMORY.md"

# Заголовок записи вида "## 2026-09-04 16:22 [20260904-162230]" — id в
# квадратных скобках, отдельно от читаемого timestamp, чтобы файл
# оставался человекочитаемым при открытии в Google Drive напрямую.
_ENTRY_HEADER_RE = re.compile(
    r"^## (?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \[(?P<id>\d{8}-\d{6})\](?P<done> ✅)?\s*$"
)


def _memory_dir() -> Path:
    path = Path(CLAUDE_MEMORY_DIR)
    if not path.is_dir():
        raise RuntimeError(
            f"Папка памяти не найдена: {CLAUDE_MEMORY_DIR}. "
            f"Проверь CLAUDE_MEMORY_DIR в .env и что junction/symlink на месте."
        )
    return path


def save_thought(summary: str) -> str:
    """Дописывает мысль строкой в черновой инбокс — без создания memory-файла.
    Возвращает id записи (для кнопки "Закрыто", см. handlers/dispatch.py)."""
    inbox_path = _memory_dir() / _INBOX_FILENAME
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")
    entry_id = now.strftime("%Y%m%d-%H%M%S")
    entry = f"## {timestamp} [{entry_id}]\n{summary.strip()}\n\n"
    with inbox_path.open("a", encoding="utf-8") as f:
        f.write(entry)
    return entry_id


def _parse_entries() -> list[dict]:
    """Разбирает memory_inbox.md на записи с ID (см. _ENTRY_HEADER_RE) —
    записи старого формата (без ID, до 2026-09-04) пропускаются, см.
    docstring модуля."""
    inbox_path = _memory_dir() / _INBOX_FILENAME
    if not inbox_path.is_file():
        return []

    text = inbox_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    entries = []
    current = None
    body_lines: list[str] = []
    for line in lines:
        match = _ENTRY_HEADER_RE.match(line)
        if match:
            if current is not None:
                current["summary"] = "\n".join(body_lines).strip()
                entries.append(current)
            current = {
                "id": match.group("id"),
                "timestamp": match.group("timestamp"),
                "done": bool(match.group("done")),
            }
            body_lines = []
        elif current is not None:
            body_lines.append(line)
    if current is not None:
        current["summary"] = "\n".join(body_lines).strip()
        entries.append(current)
    return entries


def list_open_thoughts() -> list[dict]:
    """Все записи (нового формата, с ID) без пометки "выполнено", в порядке
    добавления в файл (старые первыми)."""
    return [e for e in _parse_entries() if not e["done"]]


def list_done_thoughts() -> list[dict]:
    """Все записи с пометкой "выполнено" — показываются пользователю только
    по явному запросу, см. handlers/dispatch.py."""
    return [e for e in _parse_entries() if e["done"]]


def mark_thought_done(entry_id: str) -> bool:
    """Помечает запись как выполненную ПРЯМО В ФАЙЛЕ — дописывает " ✅" в
    конец её заголовка. Запись никуда не удаляется и не перемещается,
    только эта одна строка меняется. Возвращает False, если записи с таким
    id не нашлось (например, файл был вручную отредактирован)."""
    inbox_path = _memory_dir() / _INBOX_FILENAME
    if not inbox_path.is_file():
        return False

    text = inbox_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    found = False
    for i, line in enumerate(lines):
        match = _ENTRY_HEADER_RE.match(line)
        if match and match.group("id") == entry_id:
            if not match.group("done"):
                lines[i] = f"{line} ✅"
            found = True
            break

    if not found:
        return False

    inbox_path.write_text("\n".join(lines), encoding="utf-8")
    return True


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
