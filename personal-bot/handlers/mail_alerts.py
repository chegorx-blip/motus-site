"""
Фоновые проверки почты — вызываются планировщиком (JobQueue в main.py), не
пользователем напрямую. Проверяет все 4 ящика из config.MAILBOXES.

Два независимых алерта:
- срочная почта — каждые 30 минут, 07:30–22:30. Каждое новое непрочитанное
  письмо во всех 4 ящиках проходит через urgency_classifier (Claude решает
  срочно/нет по общим признакам + накопленным правилам пользователя) — только
  срочные пушатся сразу, с кнопками ✅/❌ под каждым письмом, чтобы
  пользователь мог поправить классификатор "на горячую" (см. resolve_urgency
  ниже — привязано к CallbackQueryHandler в main.py).
- дежурная сводка — раз в день в 08:00, все непрочитанные письма во всех 4
  ящиках за сутки одним сообщением, без классификации срочности.

"Уже показанные" письма не повторяются между прогонами срочной проверки — см.
adapters/seen_store.py. Дневная сводка НЕ помечает письма как показанные:
письмо, попавшее в утреннюю сводку, всё равно должно получить отдельный
срочный алерт позже, если сработает как срочное.
"""

import datetime
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from adapters.gmail_client import list_recent_unread
from adapters.seen_store import filter_unseen, mark_seen
from adapters.urgency_classifier import classify_urgency
from adapters.urgency_rules import add_rule
from config import ALLOWED_CHAT_ID, MAILBOXES

logger = logging.getLogger(__name__)

_MAX_SNIPPET_CHARS = 120

# JobQueue.run_repeating не умеет ограничивать проверку временем суток сама —
# только run_daily умеет конкретное время. Поэтому задача тикает каждые 30
# минут круглосуточно, а вот эта проверка внутри решает, ночью это или нет,
# и просто ничего не делает вне окна 07:30–22:30 (см. main.py — тот же
# интервал задан там же для регистрации задачи; окно — только здесь, чтобы
# этот файл был самодостаточным и его можно было понять, не заглядывая в
# main.py).
_URGENT_WINDOW_START = datetime.time(hour=7, minute=30)
_URGENT_WINDOW_END = datetime.time(hour=22, minute=30)

# callback_data кнопок несёт только id письма (mailbox_id:gmail_id) — тема и
# отправитель туда не поместятся (у Telegram лимит 64 байта на callback_data).
# Сама карточка (sender/subject) лежит в bot_data по этому id, callback
# использует ключ только для того, чтобы её найти. bot_data (не user_data) —
# потому что алерт присылает фоновая задача (JobQueue), а не сообщение
# пользователя, у которого был бы context.user_data этого конкретного чата.
_PENDING_URGENCY_KEY = "pending_urgency_feedback"


def _within_urgent_window() -> bool:
    now = datetime.datetime.now().time()
    return _URGENT_WINDOW_START <= now <= _URGENT_WINDOW_END


def _format_line(mail: dict) -> str:
    snippet = mail["snippet"]
    if len(snippet) > _MAX_SNIPPET_CHARS:
        snippet = snippet[:_MAX_SNIPPET_CHARS] + "…"
    mailbox_label = MAILBOXES.get(mail["mailbox_id"], mail["mailbox_id"])
    return f"• *{mail['subject']}*\n  от {mail['sender']} ({mailbox_label})\n  {snippet}"


def _collect_all_unread() -> list[dict]:
    """Непрочитанные письма за сутки по всем 4 ящикам сразу, одним плоским
    списком — ошибка в одном ящике (например токен ещё не выпущен) не должна
    останавливать проверку остальных."""
    all_mails = []
    for mailbox_id in MAILBOXES:
        try:
            all_mails.extend(list_recent_unread(mailbox_id))
        except Exception:
            logger.exception("Не удалось проверить ящик %s", mailbox_id)
    return all_mails


async def check_urgent_mail(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _within_urgent_window():
        return

    all_mails = _collect_all_unread()
    new_ids = set(filter_unseen([m["id"] for m in all_mails]))
    new_mails = [m for m in all_mails if m["id"] in new_ids]
    if not new_mails:
        return

    seen_ids = []
    for mail in new_mails:
        seen_ids.append(mail["id"])
        try:
            verdict = classify_urgency(mail["sender"], mail["subject"], mail["snippet"])
        except Exception:
            logger.exception("Не удалось оценить срочность письма %s", mail["id"])
            continue

        if not verdict.get("urgent"):
            continue

        feedback_id = mail["id"]
        context.bot_data.setdefault(_PENDING_URGENCY_KEY, {})[feedback_id] = {
            "sender": mail["sender"],
            "subject": mail["subject"],
        }
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ верно, срочное", callback_data=f"urgency:yes:{feedback_id}"),
                    InlineKeyboardButton("❌ нет, не срочное", callback_data=f"urgency:no:{feedback_id}"),
                ]
            ]
        )
        text = f"🚨 Срочная почта:\n\n{_format_line(mail)}\n\n_{verdict.get('reason', '')}_"
        await context.bot.send_message(
            chat_id=ALLOWED_CHAT_ID, text=text, parse_mode="Markdown", reply_markup=keyboard
        )

    mark_seen(seen_ids)


async def handle_urgency_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие ✅/❌ под срочным алертом — запоминает оценку пользователя как
    правило на будущее (см. adapters/urgency_rules.py) и убирает кнопки."""
    query = update.callback_query
    await query.answer()

    _, verdict, feedback_id = query.data.split(":", 2)
    pending = context.bot_data.get(_PENDING_URGENCY_KEY, {})
    mail_info = pending.pop(feedback_id, None)

    if mail_info is None:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    add_rule(mail_info["sender"], mail_info["subject"], urgent=(verdict == "yes"))
    confirmation = "✅ Запомнил: это было срочное." if verdict == "yes" else "❌ Запомнил: это не срочное."
    # Markdown исходного текста (жирное/курсив) при edit сохраняем тем же
    # parse_mode — иначе звёздочки/подчёркивания из карточки письма
    # отобразятся сырыми символами вместо форматирования.
    await query.edit_message_text(
        f"{query.message.text_markdown}\n\n{confirmation}", parse_mode="Markdown"
    )


async def send_daily_mail_summary(context: ContextTypes.DEFAULT_TYPE) -> None:
    all_mails = _collect_all_unread()

    if not all_mails:
        await context.bot.send_message(
            chat_id=ALLOWED_CHAT_ID, text="📭 Дежурная почта: новых непрочитанных писем нет."
        )
        return

    lines = "\n\n".join(_format_line(m) for m in all_mails)
    text = f"📬 Дежурная почта за сутки ({len(all_mails)}):\n\n{lines}"
    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=text, parse_mode="Markdown")
