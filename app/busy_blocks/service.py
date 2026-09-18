from sqlalchemy import select
from sqlalchemy.orm import Session

from app.busy_blocks.models import BusyBlock
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


def update(db: Session, block: BusyBlock, data: BusyBlockInput) -> BusyBlock:
    for field, value in data.model_dump().items():
        setattr(block, field, value)
    db.commit()
    db.refresh(block)
    return block


def delete(db: Session, block: BusyBlock) -> None:
    db.delete(block)
    db.commit()
