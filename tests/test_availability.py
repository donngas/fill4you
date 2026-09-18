from datetime import datetime, time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.accounts.models import User
from app.availability.service import desired_mask
from app.bookmarklet import service as bookmarklet_service
from app.busy_blocks.models import BusyBlock
from app.core.rate_limit import FixedWindowRateLimiter


def test_desired_mask_excludes_busy_recurring_slots() -> None:
    block = BusyBlock(
        user_id=1,
        source="timetable",
        title="Algorithms",
        is_recurring=True,
        weekday=0,
        start_time=time(10),
        end_time=time(11, 30),
    )

    slots = [
        datetime.fromisoformat("2026-09-21T09:50:00+09:00"),
        datetime.fromisoformat("2026-09-21T12:00:00+09:00"),
    ]
    assert desired_mask([block], slots) == [False, True]


def test_desired_mask_excludes_any_slot_that_overlaps_busy_time() -> None:
    block = BusyBlock(
        user_id=1,
        source="manual",
        title="Appointment",
        is_recurring=True,
        weekday=4,
        start_time=time(14, 20),
        end_time=time(15, 20),
    )
    slots = [
        datetime.fromisoformat("2026-09-18T14:15:00+09:00"),
        datetime.fromisoformat("2026-09-18T15:15:00+09:00"),
        datetime.fromisoformat("2026-09-18T15:30:00+09:00"),
    ]

    assert desired_mask([block], slots) == [False, False, False]


def test_desired_mask_includes_before_and_after_buffers() -> None:
    block = BusyBlock(
        user_id=1,
        source="manual",
        title="Appointment",
        is_recurring=True,
        weekday=0,
        start_time=time(10),
        end_time=time(11),
        before_buffer_minutes=30,
        after_buffer_minutes=15,
    )
    slots = [
        datetime.fromisoformat("2026-09-21T09:15:00+09:00"),
        datetime.fromisoformat("2026-09-21T09:30:00+09:00"),
        datetime.fromisoformat("2026-09-21T11:15:00+09:00"),
    ]

    assert desired_mask([block], slots) == [True, False, True]


def test_availability_endpoint_uses_scoped_token(client: TestClient, db_session: Session) -> None:
    user = User(email="student@example.com", display_name="Student")
    db_session.add(user)
    db_session.flush()
    block = BusyBlock(
        user_id=user.id,
        source="manual",
        title="Appointment",
        is_recurring=True,
        weekday=0,
        start_time=time(10),
        end_time=time(11),
    )
    db_session.add(block)
    db_session.commit()
    token, raw_token = bookmarklet_service.create_token(db_session, user.id, "Test token")
    payload = {"slots": ["2026-09-21T10:30:00+09:00", "2026-09-21T12:00:00+09:00"]}

    response = client.post(
        "/api/v1/availability/when2meet",
        json=payload,
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "desired": [False, True],
        "busy_blocks": [{"id": block.id, "title": "Appointment", "slot_indexes": [0]}],
    }

    assert bookmarklet_service.revoke_token(db_session, user.id, token.id)
    revoked = client.post(
        "/api/v1/availability/when2meet",
        json=payload,
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert revoked.status_code == 401


def test_bookmarklet_script_keeps_when2meet_adapter_isolated(client: TestClient) -> None:
    response = client.get("/bookmarklet/script.js?token=test-token")

    assert response.status_code == 200
    assert "validatePage" in response.text
    assert "applyAvailability" in response.text
    assert "TimeOfSlot" in response.text
    assert "getBoundingClientRect" in response.text
    assert "range.start.element" in response.text
    assert "showPreview" in response.text
    assert "getPreviewSlots" in response.text
    assert "fill4you-preview-add" in response.text
    assert "fill4you-preview-busy" in response.text
    assert "fill4you-busy-label" in response.text
    assert "fill4you-preview-panel" in response.text


def test_availability_rate_limiter_allows_normal_retries_then_throttles() -> None:
    limiter = FixedWindowRateLimiter(limit=30, window_seconds=60)
    for _ in range(30):
        assert limiter.retry_after("a-token") is None

    assert limiter.retry_after("a-token") is not None
