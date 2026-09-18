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


def test_allows_recurring_interval_that_ends_the_following_day() -> None:
    block = BusyBlockInput(
        source="timetable",
        title="Sleep",
        is_recurring=True,
        weekday=0,
        start_time=time(23, 30),
        end_time=time(8, 30),
    )

    assert block.end_time == time(8, 30)


def test_rejects_zero_length_recurring_interval() -> None:
    with pytest.raises(ValidationError, match="cannot start and end at the same time"):
        BusyBlockInput(
            source="timetable",
            title="Algorithms",
            is_recurring=True,
            weekday=0,
            start_time=time(12),
            end_time=time(12),
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


def test_creates_one_manual_block_per_selected_weekday(
    client: TestClient, db_session: Session
) -> None:
    csrf_token = _csrf_token(client)
    client.post("/auth/development", data={"csrf_token": csrf_token})

    response = client.post(
        "/blocks",
        data={
            "source": "manual",
            "title": "Study group",
            "schedule_type": "recurring",
            "weekdays": ["0", "2"],
            "start_time": "13:00",
            "end_time": "14:15",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    blocks = db_session.query(BusyBlock).order_by(BusyBlock.weekday).all()
    assert [(block.weekday, block.title, block.source) for block in blocks] == [
        (0, "Study group", "manual"),
        (2, "Study group", "manual"),
    ]


def test_invalid_recurring_block_returns_controlled_form_error(
    client: TestClient, db_session: Session
) -> None:
    csrf_token = _csrf_token(client)
    client.post("/auth/development", data={"csrf_token": csrf_token})

    response = client.post(
        "/blocks",
        data={
            "source": "manual",
            "title": "Zero length",
            "schedule_type": "recurring",
            "weekdays": ["0"],
            "start_time": "10:00",
            "end_time": "10:00",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    dashboard = client.get("/dashboard")
    assert "반복 일정의 시작과 종료 시간은 같을 수 없습니다." in dashboard.text
    assert db_session.query(BusyBlock).count() == 0


def test_invalid_block_source_returns_controlled_form_error(
    client: TestClient, db_session: Session
) -> None:
    csrf_token = _csrf_token(client)
    client.post("/auth/development", data={"csrf_token": csrf_token})

    response = client.post(
        "/blocks",
        data={
            "source": "invalid",
            "title": "Invalid source",
            "schedule_type": "recurring",
            "weekdays": ["0"],
            "start_time": "10:00",
            "end_time": "11:00",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    dashboard = client.get("/dashboard")
    assert "일정 출처를 확인해 주세요." in dashboard.text
    assert db_session.query(BusyBlock).count() == 0


def test_resets_only_the_current_users_timetable(client: TestClient, db_session: Session) -> None:
    csrf_token = _csrf_token(client)
    client.post("/auth/development", data={"csrf_token": csrf_token})
    user = db_session.query(User).one()
    db_session.add_all(
        [
            BusyBlock(
                user_id=user.id,
                source="timetable",
                title="Class",
                is_recurring=True,
                weekday=0,
                start_time=time(10),
                end_time=time(11),
            ),
            BusyBlock(
                user_id=user.id,
                source="manual",
                title="Appointment",
                is_recurring=True,
                weekday=1,
                start_time=time(10),
                end_time=time(11),
            ),
        ]
    )
    db_session.commit()

    response = client.post("/blocks/timetable/reset", data={"csrf_token": csrf_token})

    assert response.status_code == 200
    assert [block.source for block in db_session.query(BusyBlock).all()] == ["manual"]


def test_form_actions_require_a_valid_csrf_token(client: TestClient) -> None:
    rejected = client.post("/auth/development")
    assert rejected.status_code == 403

    csrf_token = _csrf_token(client)
    accepted = client.post("/auth/development", data={"csrf_token": csrf_token})
    assert accepted.status_code == 200
