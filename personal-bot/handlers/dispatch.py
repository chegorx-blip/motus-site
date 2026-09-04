"""
Общая точка входа для распознанного текста — неважно, пришёл он из голосового
(через Whisper) или был напечатан обычным текстом. Решает две вещи:

1. Если бот только что задал уточняющий вопрос (например, "какое событие
   отменить?" или "перенос или новое событие?") — проверяет, не является ли
   текущее сообщение ответом на него, и если да — сразу выполняет выбор, не
   гоняя текст через полную классификацию заново.
2. Иначе — обычная классификация (событие / перенос / отмена / мысль / почта /
   поиск запчасти / неясно). Мысль (thought) сохраняется в память Claude Code —
   черновиком в инбокс по умолчанию, или сразу полноценной записью, если
   пользователь явно попросил запомнить (см. handlers/thought.py). Почта (mail)
   ищет письма по всем 4 ящикам по запросу пользователя (см.
   handlers/mail_search.py) — не путать с фоновыми алертами
   (handlers/mail_alerts.py), это разные независимые пути.

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

from adapters.memory_client import list_done_thoughts, list_open_thoughts, mark_thought_done
from classifier import classify
from config import TOPIC_BY_MESSAGE_TYPE, TOPIC_BY_PROJECT, TOPIC_TASKS
from handlers.balance import get_oracle_spend_this_month
from handlers.cancel_event import PENDING_KEY as _CANCEL_PENDING_KEY
from handlers.cancel_event import handle_cancel_event
from handlers.cancel_event import resolve_pending_choice as _resolve_cancel_choice
from handlers.event import PENDING_KEY as _EVENT_DUP_PENDING_KEY
from handlers.event import handle_event
from handlers.event import resolve_pending_duplicate_check as _resolve_event_dup
from handlers.mail_search import handle_mail_search
from handlers.reschedule_event import PENDING_KEY as _RESCHEDULE_PENDING_KEY
from handlers.reschedule_event import handle_reschedule_event
from handlers.reschedule_event import resolve_pending_choice as _resolve_reschedule_choice
from handlers.thought import handle_thought

_STUB_REPLIES = {
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


def _topic_for(message_type: str, project: str) -> int | None:
    """Тема Telegram-группы, куда должен уйти ОТВЕТ бота — по смыслу
    сообщения (config.TOPIC_BY_MESSAGE_TYPE/TOPIC_BY_PROJECT), не по тому,
    в какой теме пользователь написал исходное сообщение. Пользователь
    явно попросил такое поведение 2026-09-03 — иначе мысль, написанная в
    "Почте", осталась бы там же, а не ушла в "Задачи"/"AutoExpert"/"Motus".

    "thought" — особый случай: тема зависит от classifier.py's поля
    "project" (autoexpert/motus/none), не только от типа — TOPIC_TASKS как
    дефолт для project="none" или для мыслей, где LLM не смог определить
    проект по смыслу.

    None означает "не удалось определить тему" (message_type вне известных
    — например "unclear") — вызывающий код тогда не передаёт
    message_thread_id вовсе, и Telegram сам кладёт ответ в тему исходного
    сообщения (обычное поведение reply)."""
    if message_type == "thought":
        return TOPIC_BY_PROJECT.get(project, TOPIC_TASKS)
    return TOPIC_BY_MESSAGE_TYPE.get(message_type)


async def _reply_in_topic(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, topic: int | None, **kwargs
) -> None:
    """Как update.message.reply_text, но кладёт сообщение в конкретную тему
    группы (topic), если она известна — иначе обычный reply (в тему
    исходного сообщения, штатное поведение Telegram)."""
    if topic is None:
        await update.message.reply_text(text, **kwargs)
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id, message_thread_id=topic, text=text, **kwargs
    )


# "запушь"/"запуш"/"запушено"/"запушил" и т.п. — команда пользователя сохранить
# мысль насовсем. Проверяем regex'ом по корню, а не полагаемся на то, что LLM
# правильно распознает именно эту словоформу в промпте классификатора — надёжнее
# и не тратит лишний токен-вызов на то, что решается одной строкой кода.
_PUSH_COMMAND_RE = re.compile(r"запуш", re.IGNORECASE)


def _is_push_command(text: str) -> bool:
    return bool(_PUSH_COMMAND_RE.search(text))


# Команды показа списка задач — проверяем regex'ом по корню слова, тем же
# приёмом, что и _is_push_command выше: надёжнее и быстрее, чем гонять через
# LLM-классификатор то, что решается парой ключевых слов. "невыполнен"/
# "открыт" — незакрытые задачи; "выполнен"/"закрыт" (без "не" перед ними) —
# уже сделанные. Порядок проверки важен: сначала ищем явное "не"/"незакрыт"
# перед корнем, иначе "покажи выполненные" ошибочно тоже подходило бы под
# паттерн "выполнен".
_OPEN_TASKS_RE = re.compile(
    r"(незакрыт|невыполнен|не\s+закрыт|не\s+выполнен|открыт.{0,3}\s+задач)", re.IGNORECASE
)
_DONE_TASKS_RE = re.compile(r"(выполнен|закрыт.{0,3}\s+задач)", re.IGNORECASE)


def _is_open_tasks_command(text: str) -> bool:
    return bool(_OPEN_TASKS_RE.search(text))


def _is_done_tasks_command(text: str) -> bool:
    if _is_open_tasks_command(text):
        return False
    return bool(_DONE_TASKS_RE.search(text))


# Сколько кнопок-номеров помещать в один ряд клавиатуры — компромисс между
# "не слишком узкие кнопки" и "не слишком длинный список рядов", подобрано
# на глаз для обычного экрана телефона (7-8 задач помещаются в 2 ряда).
_TASK_BUTTONS_PER_ROW = 5


def _build_task_list_text(entries: list[dict], empty_message: str) -> str:
    """Нумерует задачи (1., 2., ...) — тот же номер, что на кнопке в
    _build_task_keyboard, чтобы можно было найти нужную кнопку по номеру, а
    не считать строки/угадывать по одинаковым подписям "Закрыто" (жалоба
    пользователя 2026-09-04: 7 неотличимых кнопок подряд)."""
    if not entries:
        return empty_message
    lines = []
    for i, e in enumerate(entries, start=1):
        mark = "✅ " if e["done"] else ""
        lines.append(f"{mark}{i}. {e['timestamp']} — {e['summary']}")
    return "\n\n".join(lines)


def _build_task_keyboard(entries: list[dict]) -> InlineKeyboardMarkup | None:
    """Кнопки "Закрыть №N" под ещё не закрытыми задачами — номер совпадает с
    номером в тексте (_build_task_list_text), несколько в ряд (см.
    _TASK_BUTTONS_PER_ROW), а не одна колонка из одинаковых "Закрыто" —
    так кнопка находится по номеру задачи, не по счёту строк сверху вниз.
    callback_data несёт только id записи (не номер — номер зависит от
    порядка в конкретном списке и не годится как постоянный идентификатор),
    см. adapters/memory_client.mark_thought_done."""
    open_entries = [(i, e) for i, e in enumerate(entries, start=1) if not e["done"]]
    if not open_entries:
        return None

    rows = []
    for start in range(0, len(open_entries), _TASK_BUTTONS_PER_ROW):
        chunk = open_entries[start : start + _TASK_BUTTONS_PER_ROW]
        rows.append(
            [
                InlineKeyboardButton(f"№{i}", callback_data=f"task_done:{e['id']}")
                for i, e in chunk
            ]
        )
    return InlineKeyboardMarkup(rows)


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

    # Списки задач — проверяем regex'ом ДО классификации через LLM (тот же
    # приём, что _is_push_command): "покажи невыполненные"/"открытые
    # задачи" и "покажи выполненные"/"закрытые задачи" не нуждаются в
    # понимании смысла, только в ключевых словах.
    if _is_open_tasks_command(text):
        entries = list_open_thoughts()
        reply_text = _build_task_list_text(entries, "Незакрытых задач нет 🎉")
        await _reply_in_topic(
            update, context, f"{prefix}{reply_text}", TOPIC_TASKS,
            reply_markup=_build_task_keyboard(entries),
        )
        return
    if _is_done_tasks_command(text):
        entries = list_done_thoughts()
        reply_text = _build_task_list_text(entries, "Выполненных задач пока нет.")
        await _reply_in_topic(update, context, f"{prefix}{reply_text}", TOPIC_TASKS)
        return

    result = classify(text)
    message_type = result.get("type", "unclear")
    topic = _topic_for(message_type, result.get("project", "none"))

    if message_type == "event":
        reply, candidates = handle_event(
            title=result["title"], date_hint=result["date_hint"], user_data=context.user_data
        )
        if candidates:
            await _reply_in_topic(
                update, context, f"{prefix}{reply}", topic,
                reply_markup=_build_choice_keyboard(len(candidates)),
            )
        else:
            await _reply_in_topic(update, context, f"{prefix}{reply}", topic)
    elif message_type == "reschedule_event":
        reply, candidates = handle_reschedule_event(
            search_query=result["search_query"],
            date_hint=result["date_hint"],
            user_data=context.user_data,
        )
        if candidates:
            await _reply_in_topic(
                update, context, f"{prefix}{reply}", topic,
                reply_markup=_build_choice_keyboard(len(candidates)),
            )
        else:
            await _reply_in_topic(update, context, f"{prefix}{reply}", topic)
    elif message_type == "cancel_event":
        reply, candidates = handle_cancel_event(
            search_query=result["search_query"], user_data=context.user_data
        )
        if candidates:
            await _reply_in_topic(
                update, context, f"{prefix}{reply}", topic,
                reply_markup=_build_choice_keyboard(len(candidates)),
            )
        else:
            await _reply_in_topic(update, context, f"{prefix}{reply}", topic)
    elif message_type == "thought":
        is_explicit_save = result.get("is_explicit_save", False) or _is_push_command(text)
        reply, entry_id = handle_thought(summary=result["summary"], is_explicit_save=is_explicit_save)
        # Кнопка "Закрыто" только для черновых мыслей (entry_id не None) —
        # explicit-save запись уже ушла в постоянную память отдельным
        # файлом, вне системы статусов задач, см. handlers/thought.py.
        keyboard = None
        if entry_id is not None:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Закрыто", callback_data=f"task_done:{entry_id}")]]
            )
        await _reply_in_topic(update, context, f"{prefix}{reply}", topic, reply_markup=keyboard)
    elif message_type == "mail":
        reply = handle_mail_search(search_query=result["search_query"])
        await _reply_in_topic(update, context, f"{prefix}{reply}", topic, parse_mode="Markdown")
    elif message_type == "balance":
        reply = get_oracle_spend_this_month()
        await _reply_in_topic(update, context, f"{prefix}{reply}", topic)
    else:
        # parts_search/unclear пока не привязаны к теме в TOPIC_BY_MESSAGE_TYPE
        # (topic будет None) — _reply_in_topic сама падает на обычный reply
        # в тему исходного сообщения.
        reply_template = _STUB_REPLIES.get(message_type, _STUB_REPLIES["unclear"])
        reply = reply_template.format(**result)
        await _reply_in_topic(update, context, f"{prefix}{reply}", topic)


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


def _button_label_for(keyboard: list[list], entry_id: str) -> str | None:
    """Находит подпись нажатой кнопки (например "№3") по её callback_data —
    нужна, чтобы всплывающее подтверждение назвало конкретную задачу, а не
    просто "что-то закрыто", когда кнопок несколько (см. handle_task_done_button)."""
    target = f"task_done:{entry_id}"
    for row in keyboard:
        for button in row:
            if button.callback_data == target:
                return button.text
    return None


async def handle_task_done_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие кнопки "Закрыть №N" под задачей в теме "Задачи". Запись
    остаётся в memory_inbox.md, только помечается " ✅" в заголовке (см.
    adapters/memory_client.mark_thought_done) — ничего не удаляется.

    Два разных случая по числу кнопок в исходном сообщении:
    - одна кнопка (свежая мысль, только что записанная) — дописываем "✅"
      прямо в текст сообщения, кнопку убираем;
    - несколько кнопок (сообщение со списком задач, см. _build_task_keyboard)
      — список слишком длинный, чтобы просто дописывать в конец: вместо
      этого показываем короткий всплывающий тост "Задача №N закрыта" и
      убираем ИМЕННО эту кнопку, остальные задачи и их кнопки остаются
      нетронутыми (пользователь может закрыть ещё несколько без пересылки
      списка заново)."""
    query = update.callback_query
    entry_id = query.data.split(":", 1)[1]
    keyboard = query.message.reply_markup.inline_keyboard if query.message.reply_markup else []
    label = _button_label_for(keyboard, entry_id)
    is_list_message = sum(len(row) for row in keyboard) > 1

    found = mark_thought_done(entry_id)
    if not found:
        await query.answer("Не нашёл эту запись — возможно, список устарел.")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    remaining_rows = [
        [b for b in row if b.callback_data != f"task_done:{entry_id}"] for row in keyboard
    ]
    remaining_rows = [row for row in remaining_rows if row]
    new_markup = InlineKeyboardMarkup(remaining_rows) if remaining_rows else None

    if is_list_message:
        await query.answer(f"✅ Задача {label or ''} закрыта".strip())
        await query.edit_message_reply_markup(reply_markup=new_markup)
        return

    await query.answer()
    await query.edit_message_text(f"{query.message.text}\n\n✅ Отмечено выполненным.")
