import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bookmarklet.models import BookmarkletToken


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_token(db: Session, user_id: int, label: str) -> tuple[BookmarkletToken, str]:
    raw_token = secrets.token_urlsafe(32)
    token = BookmarkletToken(
        user_id=user_id,
        label=label.strip() or "fill4you",
        token_digest=_digest(raw_token),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, raw_token


def list_tokens(db: Session, user_id: int) -> list[BookmarkletToken]:
    statement = (
        select(BookmarkletToken)
        .where(BookmarkletToken.user_id == user_id)
        .order_by(BookmarkletToken.id.desc())
    )
    return list(db.scalars(statement))


def authenticate_token(db: Session, raw_token: str) -> BookmarkletToken | None:
    statement = select(BookmarkletToken).where(
        BookmarkletToken.token_digest == _digest(raw_token), BookmarkletToken.revoked_at.is_(None)
    )
    token = db.scalar(statement)
    if token:
        token.last_used_at = datetime.now(timezone.utc)
        db.commit()
    return token


def revoke_token(db: Session, user_id: int, token_id: int) -> bool:
    token = db.scalar(
        select(BookmarkletToken).where(
            BookmarkletToken.id == token_id, BookmarkletToken.user_id == user_id
        )
    )
    if token is None or token.revoked_at:
        return False
    token.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True
