"""
Обработка сообщения типа "mail" — поиск письма по запросу пользователя через
Telegram (не путать с handlers/mail_alerts.py — те фоновые, без запроса).

Ищет по всем 4 ящикам сразу (config.MAILBOXES), за последние 3 дня, обычным
Gmail-поиском (search_query уже пришёл в синтаксисе Gmail от classifier.py —
from:/subject:/просто слова). Ошибка в одном ящике не должна прятать
результаты из остальных — тот же принцип, что в mail_alerts._collect_all_unread.
"""

import logging

from adapters.gmail_client import search_mail
from adapters.mail_translator import translate_mails
from config import MAILBOXES

logger = logging.getLogger(__name__)

_MAX_SNIPPET_CHARS = 150
_MAX_PER_MAILBOX = 5


def _format_line(mail: dict) -> str:
    """Тема/фрагмент — в русском переводе (subject_ru/snippet_ru, см.
    translate_mails), тема — кликабельная ссылка на письмо в правильном
    Gmail-аккаунте (mail["url"], см. adapters/gmail_client._gmail_url)."""
    subject = mail.get("subject_ru") or mail["subject"]
    snippet = mail.get("snippet_ru") or mail["snippet"]
    if len(snippet) > _MAX_SNIPPET_CHARS:
        snippet = snippet[:_MAX_SNIPPET_CHARS] + "…"
    mailbox_label = MAILBOXES.get(mail["mailbox_id"], mail["mailbox_id"])
    return (
        f"• [{subject}]({mail['url']})\n"
        f"  от {mail['sender']} ({mailbox_label})\n"
        f"  {snippet}"
    )


def handle_mail_search(search_query: str) -> str:
    if not search_query:
        return (
            "🤔 Не понял, что искать в почте — скажи, например, "
            "«найди письмо от Игоря про доступ»."
        )

    all_mails = []
    for mailbox_id in MAILBOXES:
        try:
            all_mails.extend(search_mail(mailbox_id, search_query, max_results=_MAX_PER_MAILBOX))
        except Exception:
            logger.exception("Не удалось найти письма в ящике %s", mailbox_id)

    if not all_mails:
        return f"📭 За последние 3 дня по запросу «{search_query}» ничего не нашёл."

    translated_mails = translate_mails(all_mails)
    lines = "\n\n".join(_format_line(m) for m in translated_mails)
    return f"📬 Нашёл ({len(all_mails)}):\n\n{lines}"
