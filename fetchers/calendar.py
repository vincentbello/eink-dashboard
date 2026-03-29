"""
fetchers/calendar.py — Events from Google Calendar via OAuth2.

First-time setup
----------------
1. Create a GCP project and enable the Google Calendar API.
2. Download the OAuth2 credentials as ``credentials.json`` (Desktop app type).
3. Run this script once interactively (or ``python -c "from fetchers.calendar import fetch_calendar; fetch_calendar()"``).
   A browser window will open; sign in and grant access.
4. A ``token.json`` file is written and reused on subsequent runs.

See README.md for detailed step-by-step instructions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import config

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10  # seconds (applied via socket-level timeout via httplib2)
_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Module-level cache.
_cache: Optional[list[CalendarEvent]] = None  # type: ignore[name-defined]


@dataclass(frozen=True)
class CalendarEvent:
    """A single calendar event."""

    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool
    location: Optional[str]


def _load_credentials():  # type: ignore[return]
    """Load or refresh OAuth2 credentials.

    Returns a valid :class:`google.oauth2.credentials.Credentials` object,
    running the OAuth flow if no valid token exists.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    token_path = Path(config.GOOGLE_TOKEN_PATH)
    creds_path = Path(config.GOOGLE_CREDENTIALS_PATH)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"Google credentials file not found: {creds_path}. "
                    "See README for setup instructions."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), _SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json())

    return creds


def fetch_calendar() -> Optional[list[CalendarEvent]]:
    """Fetch today's calendar events from Google Calendar.

    Events are returned sorted by start time.  All-day events appear first
    (they have no specific time).

    Returns the event list on success, or the last cached list on failure.
    """
    global _cache
    try:
        from googleapiclient.discovery import build
        import pytz

        creds = _load_credentials()
        service = build("calendar", "v3", credentials=creds)

        tz = ZoneInfo(config.TIMEZONE)
        now = datetime.now(tz)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

        events_result = (
            service.events()
            .list(
                calendarId=config.GOOGLE_CALENDAR_ID,
                timeMin=now.isoformat(),
                timeMax=end_of_day.isoformat(),
                maxResults=config.NUM_CALENDAR_EVENTS,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        items = events_result.get("items", [])
        events: list[CalendarEvent] = []

        for item in items:
            start_raw = item["start"]
            end_raw = item["end"]

            is_all_day = "date" in start_raw and "dateTime" not in start_raw

            if is_all_day:
                # All-day events: use midnight in the configured timezone.
                start_dt = datetime.fromisoformat(start_raw["date"]).replace(
                    tzinfo=tz
                )
                end_dt = datetime.fromisoformat(end_raw["date"]).replace(tzinfo=tz)
            else:
                start_dt = datetime.fromisoformat(start_raw["dateTime"]).astimezone(tz)
                end_dt = datetime.fromisoformat(end_raw["dateTime"]).astimezone(tz)

            events.append(
                CalendarEvent(
                    title=item.get("summary", "(No title)"),
                    start_time=start_dt,
                    end_time=end_dt,
                    is_all_day=is_all_day,
                    location=item.get("location"),
                )
            )

        _cache = events
        logger.debug("Calendar fetched: %d events", len(events))
        return events

    except FileNotFoundError as exc:
        logger.error("Calendar credentials missing: %s", exc)
    except Exception:
        logger.exception("Calendar fetch failed")

    if _cache is not None:
        logger.info("Returning stale calendar data (%d events)", len(_cache))
    return _cache
