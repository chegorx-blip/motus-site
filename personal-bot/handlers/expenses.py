"""
Команды показа трат ("покажи траты", "сколько потратил") и обработчик кнопки
исправления категории под карточкой распознанного чека (см. handlers/photo.py).

Распознавание фото → сохранение — в handlers/photo.py и
adapters/receipt_vision.py/expense_store.py. Этот файл — только просмотр уже
сохранённого и живая правка категории, тот же уровень ответственности, что
handlers/dispatch.py несёт для задач (list_open_thoughts/mark_thought_done).
"""

import re

from telegram import Update
from telegram.ext import ContextTypes

from adapters.expense_rules import add_rule as add_category_rule
from adapters.expense_store import list_expenses, set_expense_category
from config import TOPIC_FINANCE
from handlers.photo import build_category_keyboard

_CATEGORY_LABELS = {"none": "Личное", "autoexpert": "AutoExpert", "motus": "Motus"}

# "покажи траты"/"сколько потратил"/"покажи расходы" и т.п. — тот же приём,
# что _is_open_tasks_command в dispatch.py: ключевые слова решают быстрее и
# надёжнее, чем гонять через LLM-классификатор. Специально УЗКИЙ паттерн (не
# просто "расход" — совпало бы с "надо расходовать бюджет разумнее" и т.п.
# обычными мыслями) — только явные команды "покажи ..." / "сколько
# потратил ...".
#
# "oracle"/"сервер"/"облак" явно ИСКЛЮЧЕНЫ — такие вопросы должны уйти в
# classify() и попасть в тип "balance" (handlers/balance.py, Oracle Cloud),
# а не сюда: это разные источники данных (Oracle billing API vs чеки из
# темы "Финансы"), их нельзя перепутать.
_EXPENSES_COMMAND_RE = re.compile(
    r"(покажи\s+(трат|расход)|сколько\s+потратил)", re.IGNORECASE
)
_ORACLE_EXCLUSION_RE = re.compile(r"(oracle|сервер|облак)", re.IGNORECASE)


def is_expenses_command(text: str) -> bool:
    if _ORACLE_EXCLUSION_RE.search(text):
        return False
    return bool(_EXPENSES_COMMAND_RE.search(text))


def _format_expenses_text(expenses: list[dict]) -> str:
    if not expenses:
        return "Трат пока нет — пришли скриншот чека в тему «Финансы»."

    # Сумма по категории+валюте отдельно — разные валюты в одной категории
    # не складываются вместе (пример: часть чеков в EUR, часть в USD).
    totals: dict[tuple[str, str], float] = {}
    for e in expenses:
        key = (e["category"], e["currency"])
        totals[key] = totals.get(key, 0) + e["amount"]

    lines = []
    for e in expenses[-20:]:
        sub_mark = " 🔁" if e["is_subscription"] else ""
        label = _CATEGORY_LABELS.get(e["category"], e["category"])
        lines.append(
            f"• {e['timestamp']} — {e['service']}: {e['amount']:.2f} {e['currency']}{sub_mark} ({label})"
        )

    totals_lines = [
        f"{_CATEGORY_LABELS.get(cat, cat)}: {amount:.2f} {currency}"
        for (cat, currency), amount in sorted(totals.items())
    ]

    return (
        "\n".join(lines)
        + "\n\n💰 Итого:\n"
        + "\n".join(totals_lines)
    )


async def handle_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> None:
    expenses = list_expenses()
    text = _format_expenses_text(expenses)
    await context.bot.send_message(
        chat_id=update.effective_chat.id, message_thread_id=TOPIC_FINANCE, text=f"{prefix}{text}"
    )


async def handle_expense_category_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие кнопки категории (Личное/AutoExpert/Motus) под карточкой
    распознанного чека — меняет категорию записи и запоминает правило на
    будущее (adapters/expense_rules.py), тот же паттерн живой поправки, что
    уже работает для срочности почты в handlers/mail_alerts.py."""
    query = update.callback_query
    await query.answer()

    _, entry_id, category = query.data.split(":", 2)
    expense = set_expense_category(entry_id, category)
    if expense is None:
        return

    add_category_rule(expense["service"], category)

    label = _CATEGORY_LABELS.get(category, category)
    lines = [l for l in query.message.text.split("\n") if not l.startswith("Категория:")]
    lines.append(f"Категория: {label}")
    await query.edit_message_text(
        "\n".join(lines), reply_markup=build_category_keyboard(entry_id, category)
    )
