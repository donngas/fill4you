from datetime import datetime, timedelta

from cryptography.fernet import Fernet

from app.accounts.models import User
from app.core.config import Settings
from app.google_calendar import service
from app.shared.time import SEOUL


class FakeResponse:
    is_error = False

    def __init__(self, payload: dict):
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class FakeGoogleClient:
    def __init__(self, event: dict):
        self.event = event

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url: str, **_):
        if url.endswith("calendarList"):
            return FakeResponse({"items": [{"id": "primary"}]})
        return FakeResponse({"items": [self.event]})


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
