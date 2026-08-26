"""
Фоновые проверки почты — вызываются планировщиком (JobQueue в main.py), не
пользователем напрямую. Два независимых алерта:

- срочная почта (метка URGENT_LABEL_NAME) — каждые 30 минут, 07:30–22:30,
  пушит сразу как увидела;
- дежурная сводка — раз в день в 08:00, все непрочитанные письма во
  «Входящих» за сутки одним сообщением, без метки.

"Уже показанные" письма не повторяются между прогонами — см.
adapters/seen_store.py.
"""

import datetime
import logging

from telegram.ext import ContextTypes

from adapters.gmail_client import list_recent_unread, list_urgent_unread
from adapters.seen_store import filter_unseen, mark_seen
from config import ALLOWED_CHAT_ID

logger = logging.getLogger(__name__)

_MAX_SNIPPET_CHARS = 120

# JobQueue.run_repeating не умеет ограничивать проверку временем суток сама —
# только run_daily умеет конкретное время. Поэтому задача тикает каждые 30
# минут круглосуточно, а вот эта проверка внутри решает, ночью это или нет,
# и просто ничего не делает вне окна 07:30–22:30 (см. main.py — окно задано
# там же, повторено здесь как константы, чтобы этот файл был самодостаточным
# и его можно было понять, не заглядывая в main.py).
_URGENT_WINDOW_START = datetime.time(hour=7, minute=30)
_URGENT_WINDOW_END = datetime.time(hour=22, minute=30)


def _within_urgent_window() -> bool:
    now = datetime.datetime.now().time()
    return _URGENT_WINDOW_START <= now <= _URGENT_WINDOW_END


def _format_line(mail: dict) -> str:
    snippet = mail["snippet"]
    if len(snippet) > _MAX_SNIPPET_CHARS:
        snippet = snippet[:_MAX_SNIPPET_CHARS] + "…"
    return f"• *{mail['subject']}*\n  от {mail['sender']}\n  {snippet}"


async def check_urgent_mail(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _within_urgent_window():
        return

    try:
        urgent = list_urgent_unread()
    except Exception:
        logger.exception("Не удалось проверить срочную почту")
        return

    new_ids = filter_unseen([m["id"] for m in urgent])
    if not new_ids:
        return

    new_mails = [m for m in urgent if m["id"] in new_ids]
    lines = "\n\n".join(_format_line(m) for m in new_mails)
    text = f"🚨 Срочная почта ({len(new_mails)}):\n\n{lines}"

    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=text, parse_mode="Markdown")
    mark_seen(new_ids)


async def send_daily_mail_summary(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        recent = list_recent_unread()
    except Exception:
        logger.exception("Не удалось собрать дневную сводку почты")
        return

    if not recent:
        await context.bot.send_message(
            chat_id=ALLOWED_CHAT_ID, text="📭 Дежурная почта: новых непрочитанных писем нет."
        )
        return

    lines = "\n\n".join(_format_line(m) for m in recent)
    text = f"📬 Дежурная почта за сутки ({len(recent)}):\n\n{lines}"
    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=text, parse_mode="Markdown")
