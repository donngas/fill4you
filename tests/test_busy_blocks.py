import re
from datetime import datetime, time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.accounts.models import User
from app.busy_blocks.models import BusyBlock
from app.busy_blocks.schemas import BusyBlockInput


def _csrf_token(client: TestClient) -> str:
    response = client.get("/")
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def test_rejects_invalid_recurring_interval() -> None:
    with pytest.raises(ValidationError, match="End time must be after start time"):
        BusyBlockInput(
            source="timetable",
            title="Algorithms",
            is_recurring=True,
            weekday=0,
            start_time=time(12),
            end_time=time(10),
        )


def test_rejects_incomplete_one_time_interval() -> None:
    with pytest.raises(ValidationError, match="one-time block needs start and end"):
        BusyBlockInput(
            source="manual",
            title="Appointment",
            is_recurring=False,
            starts_at=datetime(2026, 9, 18, 10),
        )


def test_busy_block_crud_is_authenticated_and_owned(
    client: TestClient, db_session: Session
) -> None:
    unauthenticated = client.post(
        "/blocks",
        data={
            "source": "manual",
            "title": "Appointment",
            "schedule_type": "recurring",
            "weekday": "0",
            "start_time": "10:00",
            "end_time": "11:00",
        },
    )
    assert unauthenticated.status_code == 403

    csrf_token = _csrf_token(client)
    client.post("/auth/development", data={"csrf_token": csrf_token})
    created = client.post(
        "/blocks",
        data={
            "source": "timetable",
            "title": "Algorithms",
            "schedule_type": "recurring",
            "weekday": "0",
            "start_time": "10:00",
            "end_time": "11:30",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    block = db_session.query(BusyBlock).one()
    assert block.title == "Algorithms"
    assert block.user_id > 0

    other_user = User(email="other@example.com", display_name="Other")
    db_session.add(other_user)
    db_session.commit()
    other_block = BusyBlock(
        user_id=other_user.id,
        source="manual",
        title="Private",
        is_recurring=True,
        weekday=1,
        start_time=time(9),
        end_time=time(10),
    )
    db_session.add(other_block)
    db_session.commit()

    forbidden = client.post(f"/blocks/{other_block.id}/delete", data={"csrf_token": csrf_token})
    assert forbidden.status_code == 404


def test_creates_one_timetable_block_per_selected_weekday(
    client: TestClient, db_session: Session
) -> None:
    csrf_token = _csrf_token(client)
    client.post("/auth/development", data={"csrf_token": csrf_token})

    response = client.post(
        "/blocks",
        data={
            "source": "timetable",
            "title": "Algorithms",
            "schedule_type": "recurring",
            "weekdays": ["1", "3"],
            "start_time": "13:00",
            "end_time": "14:15",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    blocks = db_session.query(BusyBlock).order_by(BusyBlock.weekday).all()
    assert [(block.weekday, block.title) for block in blocks] == [
        (1, "Algorithms"),
        (3, "Algorithms"),
    ]


def test_form_actions_require_a_valid_csrf_token(client: TestClient) -> None:
    rejected = client.post("/auth/development")
    assert rejected.status_code == 403

    csrf_token = _csrf_token(client)
    accepted = client.post("/auth/development", data={"csrf_token": csrf_token})
    assert accepted.status_code == 200
