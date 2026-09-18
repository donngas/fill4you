import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.busy_blocks.models import BusyBlock
from app.core.config import Settings
from app.google_calendar.models import GoogleCalendarEventState, GoogleOAuthToken
from app.shared.time import SEOUL, as_seoul_time

GOOGLE_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleCalendarError(Exception):
    pass


@dataclass(frozen=True)
class SyncResult:
    created: int = 0
    updated: int = 0
    skipped_local_changes: int = 0
    removed: int = 0


def _fernet(settings: Settings) -> Fernet:
    if not settings.google_token_encryption_key:
        raise GoogleCalendarError("GOOGLE_TOKEN_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(settings.google_token_encryption_key.encode())
    except (TypeError, ValueError) as error:
        raise GoogleCalendarError("GOOGLE_TOKEN_ENCRYPTION_KEY is invalid") from error


def save_token(db: Session, user_id: int, token: dict[str, Any], settings: Settings) -> None:
    encrypted = _fernet(settings).encrypt(json.dumps(token).encode()).decode()
    credential = db.get(GoogleOAuthToken, user_id)
    if credential is None:
        credential = GoogleOAuthToken(user_id=user_id, encrypted_token=encrypted)
        db.add(credential)
    else:
        credential.encrypted_token = encrypted
    db.commit()


def has_token(db: Session, user_id: int) -> bool:
    return db.get(GoogleOAuthToken, user_id) is not None


def connected_user_ids(db: Session) -> list[int]:
    return list(db.scalars(select(GoogleOAuthToken.user_id)))


def exclude_event(db: Session, user_id: int, external_event_id: str) -> None:
    state = db.scalar(
        select(GoogleCalendarEventState).where(
            GoogleCalendarEventState.user_id == user_id,
            GoogleCalendarEventState.external_event_id == external_event_id,
        )
    )
    if state is None:
        db.add(
            GoogleCalendarEventState(
                user_id=user_id, external_event_id=external_event_id, is_excluded=True
            )
        )
    else:
        state.is_excluded = True
    db.commit()


def _load_token(db: Session, user_id: int, settings: Settings) -> dict[str, Any]:
    credential = db.get(GoogleOAuthToken, user_id)
    if credential is None:
        raise GoogleCalendarError("Google Calendar connection not found. Sign in again.")
    try:
        return json.loads(_fernet(settings).decrypt(credential.encrypted_token.encode()))
    except (InvalidToken, json.JSONDecodeError) as error:
        raise GoogleCalendarError("Stored Google Calendar credentials cannot be read") from error


def _save_loaded_token(
    db: Session, user_id: int, token: dict[str, Any], settings: Settings
) -> None:
    save_token(db, user_id, token, settings)


def _fresh_access_token(
    db: Session, user_id: int, settings: Settings, client: httpx.Client
) -> str:
    token = _load_token(db, user_id, settings)
    expires_at = token.get("expires_at")
    valid_access_token = not expires_at or float(expires_at) > datetime.now().timestamp() + 60
    if token.get("access_token") and valid_access_token:
        return str(token["access_token"])
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise GoogleCalendarError("Google access expired. Sign out and sign in again.")
    response = client.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if response.is_error:
        raise GoogleCalendarError("Google Calendar access could not be refreshed")
    refreshed = response.json()
    token.update(refreshed)
    token["refresh_token"] = refresh_token
    if "expires_in" in refreshed:
        token["expires_at"] = datetime.now().timestamp() + float(refreshed["expires_in"])
    _save_loaded_token(db, user_id, token, settings)
    return str(token["access_token"])


def _parse_event_boundary(value: dict[str, Any], *, end: bool) -> datetime:
    if "dateTime" in value:
        parsed = datetime.fromisoformat(str(value["dateTime"]).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            timezone = ZoneInfo(value.get("timeZone") or "Asia/Seoul")
            parsed = parsed.replace(tzinfo=timezone)
        return parsed.astimezone(SEOUL)
    day = date.fromisoformat(str(value["date"]))
    return datetime.combine(day, time.min, tzinfo=SEOUL)


def _event_block(calendar_id: str, event: dict[str, Any]) -> dict[str, Any] | None:
    if event.get("status") == "cancelled" or event.get("transparency") == "transparent":
        return None
    if not event.get("id") or not event.get("start") or not event.get("end"):
        return None
    starts_at = _parse_event_boundary(event["start"], end=False)
    ends_at = _parse_event_boundary(event["end"], end=True)
    if ends_at <= starts_at:
        return None
    return {
        "external_event_id": f"{calendar_id}|{event['id']}",
        "title": str(event.get("summary") or "제목 없음"),
        "starts_at": starts_at,
        "ends_at": ends_at,
    }


def _list_events(
    client: httpx.Client, access_token: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {access_token}"}
    calendars_response = client.get(f"{GOOGLE_API}/users/me/calendarList", headers=headers)
    if calendars_response.is_error:
        raise GoogleCalendarError("Google calendar list could not be read")
    events: list[dict[str, Any]] = []
    for calendar in calendars_response.json().get("items", []):
        calendar_id = calendar.get("id")
        if not calendar_id:
            continue
        page_token: str | None = None
        while True:
            response = client.get(
                f"{GOOGLE_API}/calendars/{quote(str(calendar_id), safe='')}/events",
                headers=headers,
                params={
                    "timeMin": start.isoformat(),
                    "timeMax": end.isoformat(),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "showDeleted": "false",
                    "maxResults": "2500",
                    **({"pageToken": page_token} if page_token else {}),
                },
            )
            if response.is_error:
                raise GoogleCalendarError("Google Calendar events could not be read")
            events.extend(
                item
                for item in (
                    _event_block(str(calendar_id), event)
                    for event in response.json().get("items", [])
                )
                if item is not None
            )
            page_token = response.json().get("nextPageToken")
            if not page_token:
                break
    return events


def sync_for_user(
    db: Session, user_id: int, settings: Settings, *, overwrite_local_changes: bool = False
) -> SyncResult:
    if not settings.google_calendar_configured:
        raise GoogleCalendarError("Google Calendar sync is not configured")
    now = datetime.now(SEOUL)
    window_start = now - timedelta(days=settings.google_sync_past_days)
    window_end = now + timedelta(days=settings.google_sync_future_days)
    try:
        with httpx.Client(timeout=15.0) as client:
            access_token = _fresh_access_token(db, user_id, settings, client)
            events = _list_events(client, access_token, window_start, window_end)
    except httpx.HTTPError as error:
        raise GoogleCalendarError("Google Calendar could not be reached") from error

    remote_ids = {event["external_event_id"] for event in events}
    existing = {
        block.external_event_id: block
        for block in db.scalars(
            select(BusyBlock).where(
                BusyBlock.user_id == user_id, BusyBlock.source == "google_calendar"
            )
        )
        if block.external_event_id
    }
    states = {
        state.external_event_id: state
        for state in db.scalars(
            select(GoogleCalendarEventState).where(GoogleCalendarEventState.user_id == user_id)
        )
    }
    result = SyncResult()
    for event in events:
        external_id = event["external_event_id"]
        state = states.get(external_id)
        block = existing.get(external_id)
        if state and state.is_excluded and not overwrite_local_changes:
            continue
        if block is None:
            db.add(
                BusyBlock(
                    user_id=user_id,
                    source="google_calendar",
                    title=event["title"],
                    is_recurring=False,
                    starts_at=event["starts_at"],
                    ends_at=event["ends_at"],
                    external_event_id=external_id,
                    is_locally_modified=False,
                )
            )
            result = SyncResult(
                result.created + 1,
                result.updated,
                result.skipped_local_changes,
                result.removed,
            )
            continue
        if block.is_locally_modified and not overwrite_local_changes:
            result = SyncResult(
                result.created,
                result.updated,
                result.skipped_local_changes + 1,
                result.removed,
            )
            continue
        block.title = event["title"]
        block.starts_at = event["starts_at"]
        block.ends_at = event["ends_at"]
        block.is_locally_modified = False
        if state and state.is_excluded:
            state.is_excluded = False
        result = SyncResult(
            result.created,
            result.updated + 1,
            result.skipped_local_changes,
            result.removed,
        )

    for external_id, block in existing.items():
        if external_id in remote_ids or block.is_locally_modified:
            continue
        if block.starts_at and window_start <= as_seoul_time(block.starts_at) < window_end:
            db.delete(block)
            result = SyncResult(
                result.created,
                result.updated,
                result.skipped_local_changes,
                result.removed + 1,
            )
    db.commit()
    return result
