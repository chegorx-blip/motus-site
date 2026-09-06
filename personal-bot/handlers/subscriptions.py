"""
Напоминания о повторяющихся подписках (Google One, Netflix и т.п.) —
продолжение handlers/photo.py/adapters/expense_store.py.

Два независимых куска:
1. Кнопки периода ("Месяц"/"Год"/"Разово") под карточкой чека, если Vision
   не нашёл на самом чеке явную дату следующего списания (обычный случай —
   чеки почти всегда показывают дату ТЕКУЩЕГО платежа, не следующего, см.
   adapters/receipt_vision.py). Выбор периода вычисляет дату сам: дата чека
   + месяц/год.
2. Фоновая проверка (JobQueue.run_daily в main.py, тот же механизм, что
   send_daily_mail_summary для почты) — раз в день смотрит, у каких
   подписок next_billing_date подходит в ближайшие _REMINDER_DAYS_BEFORE
   дней, шлёт напоминание в тему "Финансы" и сдвигает дату на следующий
   период (тот же period, что был выбран изначально — храним period в
   самой записи, чтобы сдвигать автоматически без повторного вопроса).
"""

import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from adapters.expense_store import (
    list_due_subscriptions,
    list_expenses,
    mark_reminded,
    set_expense_next_billing_date,
)
from config import ALLOWED_CHAT_ID, TOPIC_FINANCE

# За сколько дней до списания слать напоминание — пользователь явно попросил
# "за пару дней до даты" 2026-09-06.
_REMINDER_DAYS_BEFORE = 2

_PERIOD_DAYS = {"month": 30, "year": 365}
_PERIOD_LABELS = {"month": "Месяц", "year": "Год"}


def _add_period(base_date: datetime.date, period: str) -> datetime.date:
    """Прибавляет период к дате. Используем фиксированное число дней (30/365),
    не calendar-точный "тот же день следующего месяца" — проще, и разница в
    1-2 дня не критична для напоминания за 2 дня до факта."""
    return base_date + datetime.timedelta(days=_PERIOD_DAYS[period])


def build_period_keyboard(entry_id: str) -> InlineKeyboardMarkup:
    """Кнопки выбора периода подписки — показываются ТОЛЬКО когда Vision не
    нашёл явную дату следующего списания на самом чеке (см.
    handlers/photo.py). "Разово" — пользователь передумал, это не
    регулярная подписка, для напоминаний не отслеживаем."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Месяц", callback_data=f"sub_period:{entry_id}:month"),
                InlineKeyboardButton("Год", callback_data=f"sub_period:{entry_id}:year"),
                InlineKeyboardButton("Разово", callback_data=f"sub_period:{entry_id}:none"),
            ]
        ]
    )


async def handle_subscription_period_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие Месяц/Год/Разово под карточкой чека без известной даты
    продления — вычисляет next_billing_date от ДАТЫ ЧЕКА (не от сегодня —
    чек мог быть прислан не в день оплаты) и сохраняет период тут же в
    тексте карточки, чтобы _add_period при следующем напоминании знал,
    какой период использовать (хранить period отдельным полем не стали —
    достаточно пересчитывать заново той же кнопкой при следующем разе,
    здесь только самый первый расчёт)."""
    query = update.callback_query
    await query.answer()

    _, entry_id, period = query.data.split(":", 2)
    if period == "none":
        await query.edit_message_reply_markup(reply_markup=None)
        return

    expense = next((e for e in list_expenses() if e["id"] == entry_id), None)
    if expense is None:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    receipt_date = datetime.datetime.strptime(expense["timestamp"], "%Y-%m-%d %H:%M").date()
    next_date = _add_period(receipt_date, period)
    set_expense_next_billing_date(entry_id, next_date.isoformat())

    label = _PERIOD_LABELS[period]
    lines = [l for l in query.message.text.split("\n") if not l.startswith("Следующее списание:")]
    lines.append(f"Следующее списание: {next_date.strftime('%d.%m.%Y')} ({label})")
    await query.edit_message_text("\n".join(lines), reply_markup=None)


async def check_subscription_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Фоновая проверка раз в день (см. main.py, run_daily) — напоминает о
    подписках, чья next_billing_date подходит в ближайшие
    _REMINDER_DAYS_BEFORE дней, и сдвигает дату на следующий период сама,
    чтобы напоминание повторялось циклически без участия пользователя."""
    due = list_due_subscriptions(_REMINDER_DAYS_BEFORE)
    if not due:
        return

    for expense in due:
        date_str = expense["next_billing_date"]
        billing_date = datetime.date.fromisoformat(date_str)
        await context.bot.send_message(
            chat_id=ALLOWED_CHAT_ID,
            message_thread_id=TOPIC_FINANCE,
            text=(
                f"🔁 Напоминание: {expense['service']} — {expense['amount']:.2f} "
                f"{expense['currency']} спишется {billing_date.strftime('%d.%m.%Y')}."
            ),
        )
        mark_reminded(expense["id"], date_str)

        # Сдвигаем next_billing_date на следующий период СРАЗУ (не ждём
        # фактической даты списания) — set_expense_next_billing_date заодно
        # сбрасывает reminded_for_date, так что напоминание об этой,
        # прошедшей, дате больше не всплывёт, а list_due_subscriptions
        # начнёт отсчитывать до новой. Период неизвестен напрямую (не
        # хранится отдельным полем, см. docstring
        # handle_subscription_period_button) — прикидываем по разнице между
        # старой датой и датой чека: >180 дней считаем годовой подпиской,
        # иначе месячной.
        receipt_date = datetime.datetime.strptime(expense["timestamp"], "%Y-%m-%d %H:%M").date()
        period = "year" if (billing_date - receipt_date).days > 180 else "month"
        set_expense_next_billing_date(expense["id"], _add_period(billing_date, period).isoformat())
