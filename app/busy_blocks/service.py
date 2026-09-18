from sqlalchemy import select
from sqlalchemy.orm import Session

from app.busy_blocks.models import BusyBlock, BusyBlockBufferSetting
from app.busy_blocks.schemas import BusyBlockInput


def list_for_user(db: Session, user_id: int) -> list[BusyBlock]:
    statement = select(BusyBlock).where(BusyBlock.user_id == user_id).order_by(BusyBlock.id)
    return list(db.scalars(statement))


def get_owned(db: Session, user_id: int, block_id: int) -> BusyBlock | None:
    statement = select(BusyBlock).where(BusyBlock.id == block_id, BusyBlock.user_id == user_id)
    return db.scalar(statement)


def create(db: Session, user_id: int, data: BusyBlockInput) -> BusyBlock:
    block = BusyBlock(user_id=user_id, **data.model_dump())
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def buffer_defaults(db: Session, user_id: int) -> dict[str, tuple[int, int]]:
    defaults = {source: (15, 15) for source in ("timetable", "manual", "google_calendar")}
    for setting in db.scalars(
        select(BusyBlockBufferSetting).where(BusyBlockBufferSetting.user_id == user_id)
    ):
        defaults[setting.source] = (setting.before_buffer_minutes, setting.after_buffer_minutes)
    return defaults


def update_buffer_defaults(
    db: Session,
    user_id: int,
    source: str,
    before_minutes: int,
    after_minutes: int,
    *,
    apply_existing: bool,
) -> None:
    setting = db.scalar(
        select(BusyBlockBufferSetting).where(
            BusyBlockBufferSetting.user_id == user_id, BusyBlockBufferSetting.source == source
        )
    )
    if setting is None:
        setting = BusyBlockBufferSetting(user_id=user_id, source=source)
        db.add(setting)
    setting.before_buffer_minutes = before_minutes
    setting.after_buffer_minutes = after_minutes
    if apply_existing:
        for block in db.scalars(
            select(BusyBlock).where(BusyBlock.user_id == user_id, BusyBlock.source == source)
        ):
            block.before_buffer_minutes = before_minutes
            block.after_buffer_minutes = after_minutes
    db.commit()


def update(
    db: Session, block: BusyBlock, data: BusyBlockInput, *, mark_locally_modified: bool = False
) -> BusyBlock:
    for field, value in data.model_dump().items():
        setattr(block, field, value)
    if mark_locally_modified:
        block.is_locally_modified = True
    db.commit()
    db.refresh(block)
    return block


def delete(db: Session, block: BusyBlock) -> None:
    db.delete(block)
    db.commit()
