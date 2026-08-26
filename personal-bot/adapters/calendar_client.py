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


def find_overlapping_events(start: datetime.datetime, end: datetime.datetime) -> list[dict]:
    """
    Ищет уже существующие события, пересекающиеся по времени с [start, end) —
    для предупреждения о наложении перед созданием/переносом нового события.
    Возвращает список {"id", "summary", "start"} тех, что реально накладываются
    (Google Calendar timeMin/timeMax возвращает всё, что ПЕРЕСЕКАЕТСЯ с диапазоном,
    что и нужно — событие, начавшееся раньше и ещё идущее, тоже конфликт).
    """
    service = _get_service()
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start.isoformat() + ("Z" if start.tzinfo is None else ""),
            timeMax=end.isoformat() + ("Z" if end.tzinfo is None else ""),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        item_start = item["start"].get("dateTime", item["start"].get("date", ""))
        events.append({"id": item["id"], "summary": item.get("summary", ""), "start": item_start})
    return events


_SEARCH_HORIZON_DAYS = 90
# Русские падежные окончания, чтобы сравнивать слова по общему корню, а не по
# точной форме — Google Calendar q= требует точное совпадение целого слова
# ("Фомина" не совпадёт с "Фоминой"), поэтому падёж-независимое сравнение
# делаем сами в коде поверх списка событий, а не полагаемся на q=.
_CASE_ENDINGS = (
    "ями", "ыми", "ого", "его", "ому", "ему", "ыми", "ими",
    "ей", "ой", "ом", "ем", "ах", "ях", "ию", "ья", "ие", "ов", "ев",
    "а", "я", "ы", "и", "е", "у", "ю", "ь",
)


def _stem(word: str) -> str:
    """Грубый падёж-независимый корень слова: срезает известное русское
    окончание, если слово достаточно длинное чтобы остаться узнаваемым.
    Не настоящая морфология — просто достаточно надёжно для сравнения имён
    и коротких фраз, которые тут встречаются."""
    lowered = word.lower()
    for ending in sorted(_CASE_ENDINGS, key=len, reverse=True):
        if lowered.endswith(ending) and len(lowered) - len(ending) >= 3:
            return lowered[: -len(ending)]
    return lowered


def _list_upcoming(max_results: int) -> list[dict]:
    """Все предстоящие события в ближайшие _SEARCH_HORIZON_DAYS дней, без
    текстового фильтра — сравнение по смыслу делает find_upcoming_events."""
    service = _get_service()
    now = datetime.datetime.utcnow()
    horizon = now + datetime.timedelta(days=_SEARCH_HORIZON_DAYS)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat() + "Z",
            timeMax=horizon.isoformat() + "Z",
            maxResults=250,
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


def find_upcoming_events(query: str, max_results: int = 5) -> tuple[list[dict], bool]:
    """
    Ищет предстоящие события, чьё название пересекается по смыслу со словами
    запроса — падёж-независимо (см. _stem), не полагаясь на точное совпадение
    Google Calendar q=, которое не понимает русские падежи ("Катя Фомина" в
    запросе не совпадёт с "Встреча с Катей Фоминой" в названии через q=, но
    совпадёт здесь через сравнение корней слов).

    Ранжирует по количеству совпавших слов-корней (контрольная сумма
    совпадений) — событие, где совпало больше слов запроса, идёт выше.
    Возвращает (список_событий_по_убыванию_совпадений, is_uncertain):
    - is_uncertain=False — топ-результат однозначно лучше остальных (или
      это единственное совпадение).
    - is_uncertain=True — несколько событий набрали одинаковый лучший счёт
      совпадений, нельзя надёжно выбрать одно — вызывающий код должен
      переспросить пользователя, даже если после этого возвращено одно
      событие (не только когда возвращённых событий больше одного).
    """
    query_stems = {_stem(w) for w in query.split() if w.strip()}
    if not query_stems:
        return [], False

    scored: list[tuple[int, dict]] = []
    for event in _list_upcoming(max_results):
        title_stems = {_stem(w) for w in event["summary"].split() if w.strip()}
        score = len(query_stems & title_stems)
        if score > 0:
            scored.append((score, event))

    if not scored:
        return [], False

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_score = scored[0][0]
    top_matches = [event for score, event in scored if score == top_score]

    is_uncertain = len(top_matches) > 1
    return top_matches[:max_results], is_uncertain


def delete_event(event_id: str) -> None:
    """Удаляет событие по его id (полученному из find_upcoming_events)."""
    service = _get_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()


def reschedule_event(event_id: str, new_start: datetime.datetime) -> str:
    """
    Переносит существующее событие на новое время, сохраняя его длительность
    (не удаляет и не создаёт заново — один вызов patch дешевле по API и не
    плодит дубликаты, если что-то пойдёт не так на полпути).
    Возвращает ссылку на обновлённое событие.
    """
    service = _get_service()
    existing = service.events().get(calendarId="primary", eventId=event_id).execute()

    old_start = datetime.datetime.fromisoformat(existing["start"]["dateTime"])
    old_end = datetime.datetime.fromisoformat(existing["end"]["dateTime"])
    duration = old_end - old_start
    new_end = new_start + duration

    updated = (
        service.events()
        .patch(
            calendarId="primary",
            eventId=event_id,
            body={
                "start": {"dateTime": new_start.isoformat(), "timeZone": _TIMEZONE},
                "end": {"dateTime": new_end.isoformat(), "timeZone": _TIMEZONE},
            },
        )
        .execute()
    )
    return updated.get("htmlLink", "")
