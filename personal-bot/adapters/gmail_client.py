"""
Адаптер Gmail.

Единственное место в проекте, которое знает про Gmail API. Остальной код
просто вызывает list_urgent_unread(...) / list_recent_unread(...) и получает
уже собранные короткие карточки писем.

Авторизация устроена так же, как в adapters/calendar_client.py (тот же
"паспорт" приложения google_oauth_client.json, тот же Google Cloud проект
personal-bot) — но со своим отдельным токеном-"пропуском"
google_gmail_token.json, потому что это отдельный набор разрешений (scope):
Calendar токен не даёт доступа к почте, и наоборот. При первом запуске
откроется браузер и попросит заново разрешить доступ, теперь уже к почте.

Доступ строго read-only (gmail.readonly) — бот только читает и помечает
прочитанным, никогда не отправляет и не удаляет письма.
"""

import base64
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import URGENT_LABEL_NAME

_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_CLIENT_SECRET_PATH = os.path.join(os.path.dirname(__file__), "..", "google_oauth_client.json")
_TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "google_gmail_token.json")

_service = None
_urgent_label_id_cache: str | None = None


def _get_service():
    global _service
    if _service is not None:
        return _service

    creds = None
    if os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CLIENT_SECRET_PATH, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    _service = build("gmail", "v1", credentials=creds)
    return _service


def _find_label_id(label_name: str) -> str | None:
    """Gmail-фильтры адресуют метки по id, не по имени — сначала ищем id по
    видимому названию (например "Urgent"), которое пользователь сам завёл в
    Gmail. Кэшируем — метки не переименовываются на лету между вызовами."""
    global _urgent_label_id_cache
    if _urgent_label_id_cache is not None:
        return _urgent_label_id_cache

    service = _get_service()
    result = service.users().labels().list(userId="me").execute()
    for label in result.get("labels", []):
        if label["name"].lower() == label_name.lower():
            _urgent_label_id_cache = label["id"]
            return _urgent_label_id_cache
    return None


def _extract_headers(message: dict) -> tuple[str, str]:
    headers = message.get("payload", {}).get("headers", [])
    sender = next((h["value"] for h in headers if h["name"] == "From"), "")
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(без темы)")
    return sender, subject


def _fetch_summaries(message_ids: list[str]) -> list[dict]:
    service = _get_service()
    summaries = []
    for msg_id in message_ids:
        full = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="metadata", metadataHeaders=["From", "Subject"])
            .execute()
        )
        sender, subject = _extract_headers(full)
        summaries.append(
            {
                "id": msg_id,
                "sender": sender,
                "subject": subject,
                "snippet": full.get("snippet", ""),
            }
        )
    return summaries


def list_urgent_unread() -> list[dict]:
    """
    Непрочитанные письма с меткой URGENT_LABEL_NAME (см. config.py) —
    пользователь сам заводит эту метку/фильтр в Gmail, бот только читает.
    Возвращает [] если метки ещё нет (пользователь не успел настроить) —
    не ошибка, просто пока нечего показывать.
    """
    label_id = _find_label_id(URGENT_LABEL_NAME)
    if label_id is None:
        return []

    service = _get_service()
    result = (
        service.users()
        .messages()
        .list(userId="me", labelIds=[label_id, "UNREAD"], maxResults=25)
        .execute()
    )
    message_ids = [m["id"] for m in result.get("messages", [])]
    return _fetch_summaries(message_ids)


def list_recent_unread(max_results: int = 20) -> list[dict]:
    """Непрочитанные письма во «Входящих» за последние сутки — для дневной
    сводки. Не фильтрует по метке (это все дежурные письма, срочные уже
    ушли через list_urgent_unread раньше)."""
    service = _get_service()
    result = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            q="newer_than:1d",
            maxResults=max_results,
        )
        .execute()
    )
    message_ids = [m["id"] for m in result.get("messages", [])]
    return _fetch_summaries(message_ids)
