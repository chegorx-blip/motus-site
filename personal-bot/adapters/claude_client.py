"""
Адаптер общения с Claude.

Единственное место в проекте, которое знает про Anthropic API.
Остальной код вызывает ask(text) для обычного текстового ответа,
или ask_structured(...) когда нужен гарантированно предсказуемый
формат ответа (например: "один из этих 5 типов, плюс вот эти поля").
"""

import json

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY

_client = Anthropic(api_key=ANTHROPIC_API_KEY)

MODEL = "claude-opus-5"


def ask(system_prompt: str, user_message: str) -> str:
    """Отправляет сообщение Claude с заданным системным промптом, возвращает текстовый ответ."""
    response = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def ask_structured(system_prompt: str, user_message: str, json_schema: dict) -> dict:
    """
    Как ask(), но заставляет Claude ответить строго в виде JSON по заданной схеме
    (json_schema) — используем для классификации, где важно получить предсказуемую
    структуру (тип сообщения + извлечённые поля), а не вольный текст.
    """
    response = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        output_config={"format": {"type": "json_schema", "schema": json_schema}},
    )
    for block in response.content:
        if block.type == "text":
            return json.loads(block.text)
    return {}
