"""
Адаптер Google Calendar.

Единственное место в проекте, которое знает про Google Calendar API.
Остальной код просто вызывает create_event(...) и получает ссылку на созданное событие.

Как работает авторизация (важно понять один раз):
- google_oauth_client.json — "паспорт" нашего приложения, выдан Google Cloud Console.
- При первом запуске откроется браузер, попросит войти в Google-аккаунт и разрешить
  доступ к календарю. После этого создаётся google_calendar_token.json — "пропуск",
  который используется дальше автоматически, без повторного входа в браузер.
- Оба файла — секреты, в .gitignore, никогда не попадают в git.
"""

import datetime
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_CLIENT_SECRET_PATH = os.path.join(os.path.dirname(__file__), "..", "google_oauth_client.json")
_TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "google_calendar_token.json")
_TIMEZONE = "Asia/Nicosia"

_service = None


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

    _service = build("calendar", "v3", credentials=creds)
    return _service


def create_event(
    title: str,
    start: datetime.datetime,
    duration_minutes: int = 60,
    reminders_minutes_before: list[int] | None = None,
    notes: str = "",
) -> str:
    """
    Создаёт событие в основном календаре пользователя.
    reminders_minutes_before: список напоминаний, например [60, 780] — за час и за 13 часов.
    Возвращает ссылку на созданное событие в Google Calendar.
    """
    service = _get_service()
    end = start + datetime.timedelta(minutes=duration_minutes)

    if reminders_minutes_before:
        reminders = {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": minutes} for minutes in reminders_minutes_before
            ],
        }
    else:
        reminders = {"useDefault": True}

    event_body = {
        "summary": title,
        "description": notes,
        "start": {"dateTime": start.isoformat(), "timeZone": _TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": _TIMEZONE},
        "reminders": reminders,
    }

    created = service.events().insert(calendarId="primary", body=event_body).execute()
    return created.get("htmlLink", "")


def find_upcoming_events(query: str, max_results: int = 5) -> list[dict]:
    """
    Ищет предстоящие события по совпадению в названии (Google Calendar full-text
    search — не идеальное, но простое совпадение по словам). Возвращает список
    словарей {"id": ..., "summary": ..., "start": ...} — только будущие события,
    ближайшие первыми.
    """
    service = _get_service()
    now = datetime.datetime.utcnow().isoformat() + "Z"

    result = (
        service.events()
        .list(
            calendarId="primary",
            q=query,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date", ""))
        events.append({"id": item["id"], "summary": item.get("summary", ""), "start": start})
    return events


def delete_event(event_id: str) -> None:
    """Удаляет событие по его id (полученному из find_upcoming_events)."""
    service = _get_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
