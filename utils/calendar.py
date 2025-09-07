# utils/calendar.py
import os
from datetime import timedelta
import pytz
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from utils.google_oauth import load_creds

TZ = os.environ.get("TIMEZONE", "America/New_York")

def create_event(summary: str, start_dt, end_dt=None, description: str | None = None):
    """Создаёт событие в основном календаре авторизованного пользователя."""
    creds: Credentials | None = load_creds("admin")
    if not creds:
        return False, "Google не подключён. Откройте ссылку авторизации."

    service = build("calendar", "v3", credentials=creds)
    tz = pytz.timezone(TZ)
    start_dt = tz.localize(start_dt) if start_dt.tzinfo is None else start_dt.astimezone(tz)
    if not end_dt:
        end_dt = start_dt + timedelta(minutes=60)

    event = {
        "summary": summary[:200],
        "description": (description or "")[:1000],
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    html_link = created.get("htmlLink")
    return True, html_link or "Событие создано."
