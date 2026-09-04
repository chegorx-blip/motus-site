"""
Обработчик фото — пока используется только для скриншотов чеков/подтверждений
оплаты, присланных в тему "Финансы" (config.TOPIC_FINANCE). Фото в любой
другой теме или в личном чате (до перехода на форум) — тихо игнорируется,
это осознанное ограничение первой версии: остальные темы под фото пока не
придумано что делать.

Шаги: скачать самое крупное доступное превью фото → распознать через
adapters/receipt_vision.py (Claude Vision) → сохранить в
adapters/expense_store.py → ответить карточкой с кнопками, чтобы поправить
категорию, если Vision ошибся (тот же паттерн живой поправки, что
handlers/mail_alerts.py использует для срочности почты).
"""

import os
import tempfile

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from adapters.expense_store import save_expense
from adapters.receipt_vision import analyze_receipt
from config import TOPIC_FINANCE

_CATEGORY_LABELS = {"none": "Личное", "autoexpert": "AutoExpert", "motus": "Motus"}


def build_category_keyboard(entry_id: str, current_category: str) -> InlineKeyboardMarkup:
    """Кнопка с текущей категорией показывается неактивной пометкой (✓), две
    другие — можно нажать, чтобы исправить. callback_data несёт id записи и
    новую категорию, см. handlers/expenses.handle_expense_category_button."""
    buttons = []
    for category, label in _CATEGORY_LABELS.items():
        text = f"✓ {label}" if category == current_category else label
        buttons.append(
            InlineKeyboardButton(text, callback_data=f"expense_cat:{entry_id}:{category}")
        )
    return InlineKeyboardMarkup([buttons])


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.message_thread_id != TOPIC_FINANCE:
        return

    # Telegram присылает несколько размеров одного фото — берём самое крупное
    # (последнее в списке photo, так задокументировано в Bot API).
    photo = update.message.photo[-1]
    telegram_file = await context.bot.get_file(photo.file_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        image_path = os.path.join(tmp_dir, "receipt.jpg")
        await telegram_file.download_to_drive(image_path)

        await update.message.reply_text("🧾 Разбираю чек...")
        result = analyze_receipt(image_path)

    if not result.get("is_receipt"):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            message_thread_id=TOPIC_FINANCE,
            text="🤔 Не похоже на чек или подтверждение оплаты — не нашёл, что сохранить.",
        )
        return

    entry_id = save_expense(
        service=result["service"],
        amount=result["amount"],
        currency=result["currency"],
        category=result["category"],
        is_subscription=result["is_subscription"],
        raw_summary=result["summary"],
    )

    sub_mark = " 🔁 подписка" if result["is_subscription"] else ""
    label = _CATEGORY_LABELS.get(result["category"], result["category"])
    text = (
        f"💳 {result['service']}: {result['amount']:.2f} {result['currency']}{sub_mark}\n"
        f"{result['summary']}\n"
        f"Категория: {label}"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        message_thread_id=TOPIC_FINANCE,
        text=text,
        reply_markup=build_category_keyboard(entry_id, result["category"]),
    )
