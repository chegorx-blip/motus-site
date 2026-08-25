"""
Общая точка входа для распознанного текста — неважно, пришёл он из голосового
(через Whisper) или был напечатан обычным текстом. Решает две вещи:

1. Если бот только что задал уточняющий вопрос со списком вариантов (например,
   "какое событие отменить?") — проверяет, не является ли текущее сообщение
   ответом на него ("1", "второй", "первое"), и если да — сразу выполняет выбор,
   не гоняя текст через полную классификацию заново.
2. Иначе — обычная классификация (событие / отмена / мысль / почта / поиск / неясно).
   Мысль (thought) сохраняется в память Claude Code — черновиком в инбокс по
   умолчанию, или сразу полноценной записью, если пользователь явно попросил
   запомнить (см. handlers/thought.py).

Кнопки для уточняющих вопросов собираются здесь же — единое место, где решается,
когда показывать кнопки выбора.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import re

from classifier import classify
from handlers.cancel_event import PENDING_KEY, handle_cancel_event, resolve_pending_choice
from handlers.event import handle_event
from handlers.thought import handle_thought

_STUB_REPLIES = {
    "mail": "📧 Понял, это про почту: «{summary}».\n"
    "Пока не умею работать с почтой из бота — это следующий шаг.",
    "parts_search": "🔍 Понял, это поиск запчасти: «{summary}».\n"
    "Пока не умею искать по сайтам — это следующий шаг.",
    "unclear": "🤔 Не совсем понял, что с этим делать: «{summary}».",
}


def _parse_choice_number(text: str, max_options: int) -> int | None:
    """Пытается понять, что текст — это выбор варианта: "1", "2-й", "второй" и т.п."""
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        index = int(digits) - 1
        if 0 <= index < max_options:
            return index

    words_to_number = ["перв", "втор", "трет", "четверт", "пят"]
    lowered = text.lower()
    for i, stem in enumerate(words_to_number[:max_options]):
        if stem in lowered:
            return i
    return None


_REJECTION_WORDS = ["нет", "ни один", "ни одно", "не то", "не тот", "не подходит"]


def _is_rejection(text: str) -> bool:
    """Похоже ли сообщение на отказ от всех вариантов ("нет", "ни один") без уточнения,
    что искать вместо этого."""
    lowered = text.lower().strip()
    return any(lowered == word or lowered.startswith(word) for word in _REJECTION_WORDS)


def _build_choice_keyboard(count: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(str(i + 1), callback_data=f"choice:{i}") for i in range(count)
    ]
    return InlineKeyboardMarkup([buttons])


# "запушь"/"запуш"/"запушено"/"запушил" и т.п. — команда пользователя сохранить
# мысль насовсем. Проверяем regex'ом по корню, а не полагаемся на то, что LLM
# правильно распознает именно эту словоформу в промпте классификатора — надёжнее
# и не тратит лишний токен-вызов на то, что решается одной строкой кода.
_PUSH_COMMAND_RE = re.compile(r"запуш", re.IGNORECASE)


def _is_push_command(text: str) -> bool:
    return bool(_PUSH_COMMAND_RE.search(text))


async def handle_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, prefix: str = ""
) -> None:
    pending = context.user_data.get(PENDING_KEY)
    if pending:
        choice = _parse_choice_number(text, len(pending))
        if choice is not None:
            reply = resolve_pending_choice(context.user_data, choice)
            await update.message.reply_text(f"{prefix}{reply}")
            return
        if _is_rejection(text):
            # явный отказ без уточнения, что искать вместо этого — короткий
            # понятный ответ, не гадаем и не молчим
            context.user_data.pop(PENDING_KEY, None)
            await update.message.reply_text(
                f"{prefix}🤔 Непонятно, что искать вместо этого — скажи по-другому."
            )
            return
        # текст не похож ни на номер, ни на отказ — считаем, что пользователь
        # задаёт новую команду, забываем ожидание и обрабатываем как новое сообщение
        context.user_data.pop(PENDING_KEY, None)

    result = classify(text)
    message_type = result.get("type", "unclear")

    if message_type == "event":
        reply = handle_event(title=result["title"], date_hint=result["date_hint"])
        await update.message.reply_text(f"{prefix}{reply}")
    elif message_type == "cancel_event":
        reply, candidates = handle_cancel_event(
            search_query=result["search_query"], user_data=context.user_data
        )
        if candidates:
            await update.message.reply_text(
                f"{prefix}{reply}", reply_markup=_build_choice_keyboard(len(candidates))
            )
        else:
            await update.message.reply_text(f"{prefix}{reply}")
    elif message_type == "thought":
        is_explicit_save = result.get("is_explicit_save", False) or _is_push_command(text)
        reply = handle_thought(summary=result["summary"], is_explicit_save=is_explicit_save)
        await update.message.reply_text(f"{prefix}{reply}")
    else:
        reply_template = _STUB_REPLIES.get(message_type, _STUB_REPLIES["unclear"])
        reply = reply_template.format(**result)
        await update.message.reply_text(f"{prefix}{reply}")


async def handle_choice_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие inline-кнопки с номером варианта."""
    query = update.callback_query
    await query.answer()
    choice = int(query.data.split(":")[1])
    reply = resolve_pending_choice(context.user_data, choice)
    await query.edit_message_text(reply)
