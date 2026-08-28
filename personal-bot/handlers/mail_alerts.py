"""
Фоновые проверки почты — вызываются планировщиком (JobQueue в main.py), не
пользователем напрямую. Проверяет все 4 ящика из config.MAILBOXES.

Два независимых алерта:
- срочная почта — каждые 30 минут, 07:30–22:30. Каждое новое непрочитанное
  письмо во всех 4 ящиках проходит через urgency_classifier (Claude решает
  срочно/нет по общим признакам + накопленным правилам пользователя) — все
  срочные из одного прогона уходят ОДНИМ сообщением (не по одному на письмо
  — явный запрос пользователя 2026-08-28), с отдельным рядом кнопок ✅/❌ под
  каждым письмом внутри этого сообщения, чтобы пользователь мог поправить
  классификатор "на горячую" по каждому письму независимо (см.
  handle_urgency_feedback ниже — привязано к CallbackQueryHandler в main.py).
- дежурная сводка — раз в день в 08:00, все непрочитанные письма во всех 4
  ящиках за сутки одним сообщением, без классификации срочности. Письма от
  доменов из adapters/mail_ignore_list.py (Vercel/Google-входы/рассылки/
  трекинг посылок и т.п. шум) в сводку не попадают.

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
from adapters.mail_ignore_list import is_ignored
from adapters.mail_translator import translate_mails
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

# message_id → {"header": str, "blocks": [str, ...]} — состояние текста
# каждого отправленного пакета срочных алертов, обновляемое при каждом
# ✅/❌. См. check_urgent_mail и handle_urgency_feedback.
_PENDING_MESSAGES_KEY = "pending_urgency_messages"


def _within_urgent_window() -> bool:
    now = datetime.datetime.now().time()
    return _URGENT_WINDOW_START <= now <= _URGENT_WINDOW_END


def _format_line(mail: dict) -> str:
    """Карточка письма для Telegram — тема/фрагмент берутся в русском переводе,
    если он есть в карточке (subject_ru/snippet_ru — из classify_urgency для
    срочных, из translate_mails для дневной сводки), иначе оригинал (перевод
    не должен ронять весь алерт, если сам провалился, см. mail_translator.py).
    Ссылка на письмо (mail["url"]) ведёт в правильный аккаунт Gmail — см.
    adapters/gmail_client._gmail_url."""
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

    # Одно сообщение на весь пакет срочных писем, а не одно на письмо — если
    # за 30 минут пришло сразу 4 срочных, пользователь должен увидеть один
    # отчёт с 4 карточками, не 4 отдельных пуша подряд (явный запрос
    # пользователя 2026-08-28). Кнопки ✅/❌ привязаны к КОНКРЕТНОМУ письму
    # через callback_data — Telegram разрешает несколько рядов кнопок под
    # одним сообщением, так что каждое письмо просто получает свой ряд.
    #
    # feedback_id письма → индекс его блока в blocks — используется при
    # нажатии кнопки, чтобы найти и заменить ровно этот блок. Строим по
    # ГОТОВОМУ списку blocks (не по new_mails), чтобы индекс не мог
    # разъехаться из-за писем, пропущенных как не-срочные/с ошибкой.
    blocks = []
    keyboard_rows = []
    block_index_by_feedback_id = {}
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

        # Перевод достался "бесплатно" в том же вызове classify_urgency —
        # кладём его в карточку письма, чтобы _format_line подхватил
        # subject_ru/snippet_ru вместо оригинала (см. её docstring).
        translated_mail = dict(mail)
        translated_mail["subject_ru"] = verdict.get("subject_ru")
        translated_mail["snippet_ru"] = verdict.get("snippet_ru")

        feedback_id = mail["id"]
        keyboard_rows.append(
            [
                InlineKeyboardButton("✅ верно, срочное", callback_data=f"urgency:yes:{feedback_id}"),
                InlineKeyboardButton("❌ нет, не срочное", callback_data=f"urgency:no:{feedback_id}"),
            ]
        )
        blocks.append(f"{_format_line(translated_mail)}\n_{verdict.get('reason', '')}_")
        block_index_by_feedback_id[feedback_id] = len(blocks) - 1
        context.bot_data.setdefault(_PENDING_URGENCY_KEY, {})[feedback_id] = {
            "sender": mail["sender"],
            "subject": mail["subject"],
        }

    mark_seen(seen_ids)

    if not blocks:
        return

    header = "🚨 Срочная почта:" if len(blocks) == 1 else f"🚨 Срочная почта ({len(blocks)}):"
    sent_message = await context.bot.send_message(
        chat_id=ALLOWED_CHAT_ID,
        text=f"{header}\n\n" + "\n\n".join(blocks),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )
    # Держим header + список блоков ПО ID СООБЩЕНИЯ — так handle_urgency_feedback
    # может собрать новый текст заново из актуальных блоков вместо того, чтобы
    # разбирать query.message.text_markdown обратно (Telegram реконструирует
    # Markdown из отправленного не обязательно байт-в-байт, что рисковало бы
    # сломать точный поиск подстроки).
    message_state = {"header": header, "blocks": blocks}
    context.bot_data.setdefault(_PENDING_MESSAGES_KEY, {})[sent_message.message_id] = message_state
    for feedback_id, block_index in block_index_by_feedback_id.items():
        context.bot_data[_PENDING_URGENCY_KEY][feedback_id]["message_id"] = sent_message.message_id
        context.bot_data[_PENDING_URGENCY_KEY][feedback_id]["block_index"] = block_index


async def handle_urgency_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие ✅/❌ под одним из писем в пакете срочных алертов — запоминает
    оценку пользователя как правило на будущее (см. adapters/urgency_rules.py),
    заменяет ТОЛЬКО текст этого письма подтверждением и убирает ТОЛЬКО его
    ряд кнопок — остальные письма того же сообщения (если их несколько)
    остаются нетронутыми, каждое со своими ✅/❌."""
    query = update.callback_query
    await query.answer()

    _, verdict, feedback_id = query.data.split(":", 2)
    pending = context.bot_data.get(_PENDING_URGENCY_KEY, {})
    mail_info = pending.pop(feedback_id, None)

    # Ряд кнопок, отвечающий этому feedback_id, ищем по callback_data второй
    # кнопки в ряду ("urgency:no:<feedback_id>") — так убираем именно его,
    # не полагаясь на порядок/индекс, который мог бы разъехаться.
    remaining_rows = [
        row
        for row in query.message.reply_markup.inline_keyboard
        if row[1].callback_data != f"urgency:no:{feedback_id}"
    ]
    new_markup = InlineKeyboardMarkup(remaining_rows) if remaining_rows else None

    if mail_info is None:
        await query.edit_message_reply_markup(reply_markup=new_markup)
        return

    add_rule(mail_info["sender"], mail_info["subject"], urgent=(verdict == "yes"))
    confirmation = "✅ Запомнил: это было срочное." if verdict == "yes" else "❌ Запомнил: это не срочное."

    # Текст пересобираем заново из message_state (header + список блоков),
    # обновляя ровно блок этого письма по его индексу — не пытаемся
    # разобрать/найти подстроку в query.message.text_markdown (Telegram
    # реконструирует Markdown из отправленного текста не обязательно
    # байт-в-байт, точный поиск подстроки был бы ненадёжен).
    messages = context.bot_data.get(_PENDING_MESSAGES_KEY, {})
    message_state = messages.get(query.message.message_id)
    if message_state is None:
        # Состояние потеряно (перезапуск бота между отправкой и нажатием) —
        # покажем хотя бы подтверждение отдельной строкой, не теряя факт.
        await query.edit_message_text(
            f"{query.message.text_markdown}\n\n{confirmation}",
            parse_mode="Markdown",
            reply_markup=new_markup,
        )
        return

    block_index = mail_info.get("block_index")
    if block_index is not None and block_index < len(message_state["blocks"]):
        message_state["blocks"][block_index] = f"{message_state['blocks'][block_index]}\n{confirmation}"

    new_text = f"{message_state['header']}\n\n" + "\n\n".join(message_state["blocks"])
    await query.edit_message_text(new_text, parse_mode="Markdown", reply_markup=new_markup)


async def send_daily_mail_summary(context: ContextTypes.DEFAULT_TYPE) -> None:
    all_mails = _collect_all_unread()

    # Список-игнор по домену отправителя (adapters/mail_ignore_list.py) —
    # только здесь, в дневной сводке. Срочные алерты не нуждаются в этом
    # списке (urgency_classifier уже решает по смыслу письма, не по домену),
    # а поиск по запросу не должен ничего прятать от пользователя, который
    # явно что-то ищет — см. docstring mail_ignore_list.py.
    visible_mails = [m for m in all_mails if not is_ignored(m["sender"])]

    if not visible_mails:
        await context.bot.send_message(
            chat_id=ALLOWED_CHAT_ID, text="📭 Дежурная почта: новых непрочитанных писем нет."
        )
        return

    # В отличие от срочных алертов, у дневной сводки нет своего LLM-вызова
    # (никакой классификации срочности) — перевод получаем отдельным батч-
    # вызовом на всю пачку сразу, не по одному письму (см. mail_translator.py).
    translated_mails = translate_mails(visible_mails)
    lines = "\n\n".join(_format_line(m) for m in translated_mails)
    text = f"📬 Дежурная почта за сутки ({len(visible_mails)}):\n\n{lines}"
    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=text, parse_mode="Markdown")
