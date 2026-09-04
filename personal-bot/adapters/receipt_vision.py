"""
Распознавание чеков/скриншотов оплаты через Claude Vision.

Единственное место в проекте, которое отправляет Claude изображение (не
текст) — используется только для темы "Финансы" (см. handlers/photo.py).
Тот же Anthropic-клиент, что adapters/claude_client.py, но с image content
block вместо текстового сообщения — ask_structured() того файла не подходит,
она поддерживает только текст.
"""

import base64
import json

from anthropic import Anthropic

from adapters.expense_rules import format_rules_for_prompt
from config import ANTHROPIC_API_KEY

_client = Anthropic(api_key=ANTHROPIC_API_KEY)

_MODEL = "claude-opus-5"

_SYSTEM_PROMPT_TEMPLATE = """\
Ты распознаёшь скриншоты чеков и подтверждений оплаты (Google One, Apple, \
подписки, счета за услуги и т.п.) для личного помощника пользователя.

Извлеки из изображения:
- service: название сервиса/продавца, коротко и понятно (например "Google One", \
"Netflix", "AutoExpert поставщик запчастей"). Если на скриншоте есть счёт/инвойс \
без явного названия бренда — используй название компании-отправителя.
- amount: сумма списания, число (например 4.99). Если сумм несколько — итоговая \
к оплате.
- currency: код валюты (EUR, USD, GBP и т.п.) — по символу или явному указанию \
на скриншоте.
- is_subscription: true, если это выглядит как ПОВТОРЯЮЩАЯСЯ подписка \
(есть слова "subscription", "renews", "ежемесячно", "auto-renew" и т.п. — или \
сервис общеизвестно подписочный, например Google One/Netflix/Apple iCloud), \
false — если это разовая покупка/счёт.
- category: к какому проекту относится трата — "autoexpert" (автосервис \
AutoExpert — запчасти, оборудование, поставщики для сервиса), "motus" \
(бизнес-проект Motus — импорт машин, реклама, CRM), или "none" (личное). \
Определяй по смыслу того, что на чеке — если сомневаешься, "none".
- summary: одно короткое предложение с сутью — что это за трата, для карточки \
в Telegram.

Если на изображении вообще не похоже на чек/оплату (случайный скриншот, не по \
теме) — is_receipt: false и остальные поля можно оставить пустыми/нулевыми.
{rules_block}
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "is_receipt": {"type": "boolean"},
        "service": {"type": "string"},
        "amount": {"type": "number"},
        "currency": {"type": "string"},
        "is_subscription": {"type": "boolean"},
        "category": {"type": "string", "enum": ["autoexpert", "motus", "none"]},
        "summary": {"type": "string"},
    },
    "required": [
        "is_receipt",
        "service",
        "amount",
        "currency",
        "is_subscription",
        "category",
        "summary",
    ],
    "additionalProperties": False,
}

_MEDIA_TYPE_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def analyze_receipt(image_path: str) -> dict:
    """
    Принимает путь к скачанному файлу фото (см. handlers/photo.py), возвращает
    словарь вида:
    {"is_receipt": true, "service": "Google One", "amount": 4.99,
     "currency": "EUR", "is_subscription": true, "category": "none",
     "summary": "Оплата подписки Google One"}
    """
    ext = image_path[image_path.rfind(".") :].lower()
    media_type = _MEDIA_TYPE_BY_EXT.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(rules_block=format_rules_for_prompt())

    response = _client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": "Разбери этот скриншот."},
                ],
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    for block in response.content:
        if block.type == "text":
            return json.loads(block.text)
    return {"is_receipt": False}
