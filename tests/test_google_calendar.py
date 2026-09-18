from datetime import datetime, timedelta
from urllib.parse import unquote

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.accounts import router as accounts_router
from app.accounts.models import User
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.google_calendar import service
from app.main import app
from app.shared.time import SEOUL


class FakeResponse:
    is_error = False

    def __init__(self, payload: dict):
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class FakeGoogleClient:
    def __init__(
        self,
        event: dict | None = None,
        *,
        calendars: list[dict] | None = None,
        events_by_calendar: dict[str, list[dict]] | None = None,
        event_pages: dict[str, list[list[dict]]] | None = None,
        refresh_payload: dict | None = None,
    ):
        self.calendars = calendars or [{"id": "primary", "primary": True}]
        self.events_by_calendar = events_by_calendar or {"primary": [event] if event else []}
        self.event_pages = event_pages or {}
        self.refresh_payload = refresh_payload
        self.refresh_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url: str, **kwargs):
        if url.endswith("calendarList"):
            return FakeResponse({"items": self.calendars})
        calendar_path = url.split("/calendars/", maxsplit=1)[1]
        encoded_calendar_id = calendar_path.split("/events", maxsplit=1)[0]
        calendar_id = unquote(encoded_calendar_id)
        if calendar_id in self.event_pages:
            page_index = 1 if kwargs.get("params", {}).get("pageToken") else 0
            payload = {"items": self.event_pages[calendar_id][page_index]}
            if page_index + 1 < len(self.event_pages[calendar_id]):
                payload["nextPageToken"] = "next-page"
            return FakeResponse(payload)
        return FakeResponse({"items": self.events_by_calendar.get(calendar_id, [])})

    def post(self, *_args, **_kwargs):
        self.refresh_calls += 1
        return FakeResponse(self.refresh_payload or {})


def _settings() -> Settings:
    return Settings(
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_token_encryption_key=Fernet.generate_key().decode(),
    )


def _event(title: str, starts_at: datetime, ends_at: datetime) -> dict:
    return {
        "id": "event-id",
        "summary": title,
        "start": {"dateTime": starts_at.isoformat()},
        "end": {"dateTime": ends_at.isoformat()},
    }


def test_sync_imports_events_and_preserves_local_edits(db_session, monkeypatch) -> None:
    settings = _settings()
    user = User(email="calendar@example.com", display_name="Calendar", google_subject="google-id")
    db_session.add(user)
    db_session.commit()
    now = datetime.now(SEOUL).replace(second=0, microsecond=0) + timedelta(days=1)
    first_event = _event("원래 제목", now, now + timedelta(hours=1))
    monkeypatch.setattr(service.httpx, "Client", lambda **_: FakeGoogleClient(first_event))
    service.save_token(db_session, user.id, {"access_token": "access"}, settings)

    result = service.sync_for_user(db_session, user.id, settings)
    assert result.created == 1
    block = service.BusyBlock.__table__
    imported = db_session.execute(block.select()).mappings().one()
    assert imported["title"] == "원래 제목"

    db_session.execute(
        block.update()
        .where(block.c.id == imported["id"])
        .values(title="내 제목", is_locally_modified=True)
    )
    db_session.commit()
    changed_event = _event("Google 제목", now + timedelta(hours=1), now + timedelta(hours=2))
    monkeypatch.setattr(service.httpx, "Client", lambda **_: FakeGoogleClient(changed_event))

    result = service.sync_for_user(db_session, user.id, settings)
    assert result.skipped_local_changes == 1
    assert db_session.execute(block.select()).mappings().one()["title"] == "내 제목"

    result = service.sync_for_user(db_session, user.id, settings, overwrite_local_changes=True)
    assert result.updated == 1
    assert db_session.execute(block.select()).mappings().one()["title"] == "Google 제목"


def test_sync_keeps_excluded_event_hidden(db_session, monkeypatch) -> None:
    settings = _settings()
    user = User(email="excluded@example.com", display_name="Excluded", google_subject="google-id-2")
    db_session.add(user)
    db_session.commit()
    now = datetime.now(SEOUL).replace(second=0, microsecond=0) + timedelta(days=1)
    event = _event("숨긴 일정", now, now + timedelta(hours=1))
    monkeypatch.setattr(service.httpx, "Client", lambda **_: FakeGoogleClient(event))
    service.save_token(db_session, user.id, {"access_token": "access"}, settings)
    service.exclude_event(db_session, user.id, "primary|event-id")

    result = service.sync_for_user(db_session, user.id, settings)
    assert result.created == 0
    assert db_session.query(service.BusyBlock).count() == 0


def test_sync_selects_primary_calendar_by_default_and_respects_selection(
    db_session, monkeypatch
) -> None:
    settings = _settings()
    user = User(
        email="selection@example.com", display_name="Selection", google_subject="google-id-3"
    )
    db_session.add(user)
    db_session.commit()
    now = datetime.now(SEOUL).replace(second=0, microsecond=0) + timedelta(days=1)
    client = FakeGoogleClient(
        calendars=[
            {"id": "primary", "summary": "기본", "primary": True},
            {"id": "shared@example.com", "summary": "공유"},
        ],
        events_by_calendar={
            "primary": [_event("기본 일정", now, now + timedelta(hours=1))],
            "shared@example.com": [_event("공유 일정", now, now + timedelta(hours=1))],
        },
    )
    monkeypatch.setattr(service.httpx, "Client", lambda **_: client)
    service.save_token(db_session, user.id, {"access_token": "access"}, settings)

    service.sync_for_user(db_session, user.id, settings)
    assert [block.title for block in db_session.query(service.BusyBlock).all()] == ["기본 일정"]
    calendars = service.list_calendars(db_session, user.id)
    assert [calendar.is_selected for calendar in calendars] == [True, False]

    service.update_selected_calendars(
        db_session, user.id, {"primary", "shared@example.com"}
    )
    service.sync_for_user(db_session, user.id, settings)
    assert {block.title for block in db_session.query(service.BusyBlock).all()} == {
        "기본 일정",
        "공유 일정",
    }


def test_expired_google_access_token_is_refreshed_and_remains_encrypted(db_session) -> None:
    settings = _settings()
    user = User(email="refresh@example.com", display_name="Refresh", google_subject="google-id-4")
    db_session.add(user)
    db_session.commit()
    service.save_token(
        db_session,
        user.id,
        {"access_token": "expired", "refresh_token": "refresh", "expires_at": 0},
        settings,
    )
    stored = db_session.get(service.GoogleOAuthToken, user.id)
    assert "refresh" not in stored.encrypted_token
    client = FakeGoogleClient(refresh_payload={"access_token": "fresh", "expires_in": 3600})

    assert service._fresh_access_token(db_session, user.id, settings, client) == "fresh"
    assert client.refresh_calls == 1
    assert service._load_token(db_session, user.id, settings)["refresh_token"] == "refresh"


def test_sync_handles_all_day_free_cancelled_and_paginated_events(db_session, monkeypatch) -> None:
    settings = _settings()
    user = User(email="events@example.com", display_name="Events", google_subject="google-id-5")
    db_session.add(user)
    db_session.commit()
    tomorrow = datetime.now(SEOUL).date() + timedelta(days=1)
    all_day = {
        "id": "all-day",
        "summary": "하루 종일",
        "start": {"date": tomorrow.isoformat()},
        "end": {"date": (tomorrow + timedelta(days=1)).isoformat()},
    }
    cancelled = {**all_day, "id": "cancelled", "status": "cancelled"}
    free = {**all_day, "id": "free", "transparency": "transparent"}
    later = {**all_day, "id": "later", "summary": "다음 일정"}
    client = FakeGoogleClient(event_pages={"primary": [[all_day, cancelled, free], [later]]})
    monkeypatch.setattr(service.httpx, "Client", lambda **_: client)
    service.save_token(db_session, user.id, {"access_token": "access"}, settings)

    result = service.sync_for_user(db_session, user.id, settings)
    blocks = db_session.query(service.BusyBlock).order_by(service.BusyBlock.title).all()
    assert result.created == 2
    assert [block.title for block in blocks] == ["다음 일정", "하루 종일"]
    assert all(block.starts_at.hour == 0 for block in blocks)


def test_google_oauth_callback_persists_an_encrypted_token(
    db_session: Session, monkeypatch
) -> None:
    settings = _settings()

    class FakeOAuthClient:
        async def authorize_access_token(self, _request):
            return {
                "access_token": "access",
                "refresh_token": "refresh",
                "userinfo": {"sub": "oauth-subject", "email": "oauth@example.com", "name": "OAuth"},
            }

    def override_get_db():
        yield db_session

    monkeypatch.setattr(accounts_router, "_google_client", lambda _: FakeOAuthClient())
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.get("/auth/google/callback", follow_redirects=False)
        assert response.status_code == 303
        user = db_session.query(User).filter_by(email="oauth@example.com").one()
        stored = db_session.get(service.GoogleOAuthToken, user.id)
        assert "refresh" not in stored.encrypted_token
        assert service._load_token(db_session, user.id, settings)["refresh_token"] == "refresh"
    finally:
        app.dependency_overrides.clear()
