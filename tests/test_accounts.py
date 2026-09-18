from datetime import time

from sqlalchemy.orm import Session

from app.accounts.service import get_or_create_development_user, upsert_google_user
from app.busy_blocks.models import BusyBlock


def _assert_default_sleep_blocks(db_session: Session, user_id: int) -> None:
    blocks = (
        db_session.query(BusyBlock)
        .filter_by(user_id=user_id, source="manual", title="수면")
        .order_by(BusyBlock.weekday)
        .all()
    )
    assert [block.weekday for block in blocks] == list(range(7))
    assert all(block.start_time == time(23, 30) for block in blocks)
    assert all(block.end_time == time(8, 30) for block in blocks)
    assert all(block.before_buffer_minutes == 0 for block in blocks)
    assert all(block.after_buffer_minutes == 0 for block in blocks)


def test_new_google_user_gets_default_sleep_blocks(db_session: Session) -> None:
    user = upsert_google_user(
        db_session,
        subject="google-subject",
        email="new-user@example.com",
        display_name="New User",
        picture_url=None,
    )

    _assert_default_sleep_blocks(db_session, user.id)

    upsert_google_user(
        db_session,
        subject="google-subject",
        email="new-user@example.com",
        display_name="New User",
        picture_url=None,
    )
    assert db_session.query(BusyBlock).filter_by(user_id=user.id).count() == 7


def test_new_development_user_gets_default_sleep_blocks(db_session: Session) -> None:
    user = get_or_create_development_user(db_session, "developer@example.com")

    _assert_default_sleep_blocks(db_session, user.id)
