"""
Адаптер Gmail — работает сразу с несколькими ящиками (MAILBOXES, см. config.py).

Единственное место в проекте, которое знает про Gmail API. Остальной код
просто вызывает list_recent_unread(mailbox_id) и получает уже собранные
короткие карточки писем.

Авторизация устроена так же, как в adapters/calendar_client.py (тот же
"паспорт" приложения google_oauth_client.json, тот же Google Cloud проект
personal-bot) — но каждый ящик хранит свой отдельный токен-"пропуск"
google_gmail_token_<mailbox_id>.json, потому что это разные Google-аккаунты
(один OAuth "паспорт" приложения может быть переиспользован для авторизации
нескольких разных аккаунтов — при первом запуске для каждого ящика откроется
браузер и попросит войти именно в этот аккаунт).

Доступ строго read-only (gmail.readonly) — бот только читает, никогда не
отправляет и не удаляет письма.
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_CLIENT_SECRET_PATH = os.path.join(os.path.dirname(__file__), "..", "google_oauth_client.json")

_services: dict[str, object] = {}


def _token_path(mailbox_id: str) -> str:
    return os.path.join(
        os.path.dirname(__file__), "..", f"google_gmail_token_{mailbox_id}.json"
    )


def _get_service(mailbox_id: str):
    """Возвращает (и кэширует) авторизованный Gmail-сервис для конкретного
    ящика. Первый вызов для нового mailbox_id, у которого ещё нет токен-файла,
    откроет браузер — важно тогда войти именно в аккаунт этого ящика, не в
    первый попавшийся."""
    if mailbox_id in _services:
        return _services[mailbox_id]

    token_path = _token_path(mailbox_id)
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CLIENT_SECRET_PATH, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    _services[mailbox_id] = service
    return service


def _extract_headers(message: dict) -> tuple[str, str]:
    headers = message.get("payload", {}).get("headers", [])
    sender = next((h["value"] for h in headers if h["name"] == "From"), "")
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(без темы)")
    return sender, subject


def _fetch_summaries(mailbox_id: str, message_ids: list[str]) -> list[dict]:
    service = _get_service(mailbox_id)
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
                "id": f"{mailbox_id}:{msg_id}",
                "mailbox_id": mailbox_id,
                "sender": sender,
                "subject": subject,
                "snippet": full.get("snippet", ""),
            }
        )
    return summaries


def list_recent_unread(mailbox_id: str, max_results: int = 20) -> list[dict]:
    """Непрочитанные письма во «Входящих» одного ящика за последние сутки.
    id в результате — с префиксом mailbox_id (см. _fetch_summaries), потому
    что разные ящики независимо нумеруют свои письма и одинаковый "голый" id
    из двух разных ящиков может случайно совпасть."""
    service = _get_service(mailbox_id)
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
    return _fetch_summaries(mailbox_id, message_ids)
