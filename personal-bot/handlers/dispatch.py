"""
Общая точка входа для распознанного текста — неважно, пришёл он из голосового
(через Whisper) или был напечатан обычным текстом. Решает две вещи:

1. Если бот только что задал уточняющий вопрос (например, "какое событие
   отменить?" или "перенос или новое событие?") — проверяет, не является ли
   текущее сообщение ответом на него, и если да — сразу выполняет выбор, не
   гоняя текст через полную классификацию заново.
2. Иначе — обычная классификация (событие / перенос / отмена / мысль / почта /
   поиск / неясно). Мысль (thought) сохраняется в память Claude Code —
   черновиком в инбокс по умолчанию, или сразу полноценной записью, если
   пользователь явно попросил запомнить (см. handlers/thought.py).

Три независимых типа уточняющих вопросов могут ожидать ответа (какое событие
отменить / какое перенести / это перенос или новое) — _ACTIVE_PENDING_KEYS
проверяется по порядку, только один активен одновременно на практике (бот
задаёт только один вопрос за раз), но порядок фиксирован явно, чтобы не
зависеть от случайного порядка словаря.

Кнопки для уточняющих вопросов собираются здесь же — единое место, где решается,
когда показывать кнопки выбора.
"""

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from classifier import classify
from handlers.cancel_event import PENDING_KEY as _CANCEL_PENDING_KEY
from handlers.cancel_event import handle_cancel_event
from handlers.cancel_event import resolve_pending_choice as _resolve_cancel_choice
from handlers.event import PENDING_KEY as _EVENT_DUP_PENDING_KEY
from handlers.event import handle_event
from handlers.event import resolve_pending_duplicate_check as _resolve_event_dup
from handlers.reschedule_event import PENDING_KEY as _RESCHEDULE_PENDING_KEY
from handlers.reschedule_event import handle_reschedule_event
from handlers.reschedule_event import resolve_pending_choice as _resolve_reschedule_choice
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


_NEW_EVENT_WORDS = ["нов", "отдельн", "другое"]


def _is_new_event_answer(text: str) -> bool:
    """Ответ на вопрос "перенос или новое событие?" в пользу нового события."""
    lowered = text.lower().strip()
    return any(word in lowered for word in _NEW_EVENT_WORDS)


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


async def _try_handle_pending(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, prefix: str
) -> bool:
    """
    Если бот ждёт ответ на один из уточняющих вопросов — обрабатывает его и
    возвращает True. Возвращает False, если ничего не ожидалось (вызывающий
    код должен тогда пойти по обычному пути классификации).
    """
    user_data = context.user_data

    # Вопрос "перенос или новое событие?" — свой формат ответа (не номер списка
    # кандидатов на удаление/перенос, а "новое" вместо этого), проверяем первым.
    if user_data.get(_EVENT_DUP_PENDING_KEY):
        wants_new = _is_new_event_answer(text)
        reply = _resolve_event_dup(user_data, wants_new)
        await update.message.reply_text(f"{prefix}{reply}")
        return True

    for pending_key, resolve_choice in (
        (_CANCEL_PENDING_KEY, _resolve_cancel_choice),
        (_RESCHEDULE_PENDING_KEY, _resolve_reschedule_choice),
    ):
        candidates = user_data.get(pending_key)
        if not candidates:
            continue

        choice = _parse_choice_number(text, len(candidates))
        if choice is not None:
            reply = resolve_choice(user_data, choice)
            await update.message.reply_text(f"{prefix}{reply}")
            return True
        if _is_rejection(text):
            user_data.pop(pending_key, None)
            await update.message.reply_text(
                f"{prefix}🤔 Непонятно, что искать вместо этого — скажи по-другому."
            )
            return True
        # текст не похож ни на номер, ни на отказ — считаем, что пользователь
        # задаёт новую команду, забываем ожидание и обрабатываем как новое сообщение
        user_data.pop(pending_key, None)

    return False


async def handle_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, prefix: str = ""
) -> None:
    if await _try_handle_pending(update, context, text, prefix):
        return

    result = classify(text)
    message_type = result.get("type", "unclear")

    if message_type == "event":
        reply, candidates = handle_event(
            title=result["title"], date_hint=result["date_hint"], user_data=context.user_data
        )
        if candidates:
            await update.message.reply_text(
                f"{prefix}{reply}", reply_markup=_build_choice_keyboard(len(candidates))
            )
        else:
            await update.message.reply_text(f"{prefix}{reply}")
    elif message_type == "reschedule_event":
        reply, candidates = handle_reschedule_event(
            search_query=result["search_query"],
            date_hint=result["date_hint"],
            user_data=context.user_data,
        )
        if candidates:
            await update.message.reply_text(
                f"{prefix}{reply}", reply_markup=_build_choice_keyboard(len(candidates))
            )
        else:
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
    user_data = context.user_data

    if user_data.get(_RESCHEDULE_PENDING_KEY):
        reply = _resolve_reschedule_choice(user_data, choice)
    else:
        reply = _resolve_cancel_choice(user_data, choice)
    await query.edit_message_text(reply)
